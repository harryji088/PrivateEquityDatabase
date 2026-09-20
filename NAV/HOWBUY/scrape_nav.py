#!/usr/bin/env python3
"""Batch scrape historical NAV tables from authorized Howbuy pages."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PRODUCTS = SCRIPT_DIR / "products.csv"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR.parent / "output"
DEFAULT_STATE = SCRIPT_DIR / "state" / "progress.json"
DEFAULT_PROFILE = Path.home() / ".config" / "howbuy-browser-profile"

DATE_RE = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")
NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
INVALID_FILENAME_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

NAME_COLUMNS = ("product_name", "name", "产品名称", "产品名")
URL_COLUMNS = (
    "history_url",
    "product_url",
    "url",
    "历史净值地址",
    "产品地址",
    "网页地址",
    "链接",
)

OUTPUT_FIELDS = [
    "product_name",
    "product_url",
    "history_url",
    "fund_id",
    "date",
    "unit_nav",
    "cumulative_nav",
    "change_pct",
    "scraped_at",
]

EXTRACT_HISTORY_JS = r"""
() => {
  const clean = value => (value || '').replace(/\s+/g, ' ').trim();
  const candidates = [];

  for (const table of document.querySelectorAll('table')) {
    const rows = [...table.querySelectorAll('tr')];
    let headerIndex = -1;
    let headers = [];

    for (let i = 0; i < rows.length; i++) {
      const cells = [...rows[i].querySelectorAll(':scope > th, :scope > td')]
        .map(cell => clean(cell.innerText || cell.textContent));
      const joined = cells.join('|');
      if (joined.includes('净值日期') &&
          joined.includes('单位净值') &&
          joined.includes('累计净值')) {
        headerIndex = i;
        headers = cells;
        break;
      }
    }

    if (headerIndex < 0) continue;
    const dataRows = rows.slice(headerIndex + 1).map(row =>
      [...row.querySelectorAll(':scope > td, :scope > th')]
        .map(cell => clean(cell.innerText || cell.textContent))
    ).filter(cells => cells.length > 0);
    const datedRows = dataRows.filter(cells =>
      cells.some(value => /^\d{4}[-/]\d{1,2}[-/]\d{1,2}$/.test(value))
    );
    candidates.push({headers, rows: dataRows, datedRows: datedRows.length});
  }

  if (!candidates.length) return null;
  candidates.sort((left, right) => right.datedRows - left.datedRows);
  return candidates[0];
}
"""

PREPARE_NEXT_JS = r"""
() => {
  document.querySelectorAll('[data-howbuy-next-page]').forEach(element =>
    element.removeAttribute('data-howbuy-next-page')
  );
  const visible = element => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return rect.width > 0 && rect.height > 0 &&
      style.display !== 'none' && style.visibility !== 'hidden';
  };
  const controls = [...document.querySelectorAll(
    'a, button, input[type="button"], input[type="submit"]'
  )];
  const matches = controls.map(element => {
    const text = (
      element.innerText || element.value || element.title ||
      element.getAttribute('aria-label') || ''
    ).replace(/\s+/g, '').trim();
    let score = 0;
    if (text === '下一页') score = 100;
    else if (text.includes('下一页')) score = 90;
    else if (text === '下页') score = 80;
    else if (/^(next|›|»|>)$/i.test(text)) score = 60;
    return {element, text, score};
  }).filter(item => {
    if (!item.score || !visible(item.element)) return false;
    const element = item.element;
    const classes = [element.className, element.parentElement?.className]
      .join(' ').toLowerCase();
    return !element.disabled && element.getAttribute('aria-disabled') !== 'true' &&
      !/(disabled|disable|off|nolink|unselect)/.test(classes);
  }).sort((left, right) => right.score - left.score);

  if (!matches.length) return null;
  matches[0].element.setAttribute('data-howbuy-next-page', '1');
  return {
    text: matches[0].text,
    href: matches[0].element.href || ''
  };
}
"""

CLICK_NEXT_JS = r"""
() => {
  const control = document.querySelector('[data-howbuy-next-page="1"]');
  if (!control) return false;
  control.click();
  return true;
}
"""

DIAGNOSE_PAGE_JS = r"""
() => ({
  url: location.href,
  title: document.title,
  loginPlaceholder: document.body.innerText.includes('登录可见'),
  tables: [...document.querySelectorAll('table')].map((table, index) => ({
    index,
    rows: table.querySelectorAll('tr').length,
    preview: [...table.querySelectorAll('tr')].slice(0, 4).map(row =>
      [...row.querySelectorAll(':scope > th, :scope > td')]
        .map(cell => (cell.innerText || cell.textContent || '')
          .replace(/\s+/g, ' ').trim())
    )
  })).filter(table => table.rows > 0),
  navElements: [...document.querySelectorAll('h1,h2,h3,h4,th,a,div')]
    .filter(element => /历史净值|净值日期|单位净值|累计净值/.test(
      element.innerText || element.textContent || ''
    ))
    .slice(0, 20)
    .map(element => ({
      tag: element.tagName,
      className: String(element.className || ''),
      text: (element.innerText || element.textContent || '')
        .replace(/\s+/g, ' ').trim().slice(0, 300)
    })),
  frames: [...document.querySelectorAll('iframe')].map(frame => ({
    src: frame.src || '',
    title: frame.title || '',
    name: frame.name || ''
  }))
})
"""


class ScrapeError(RuntimeError):
    """Raised when a Howbuy page cannot be parsed reliably."""


def first_value(row: Dict[str, str], names: Iterable[str]) -> str:
    for name in names:
        value = (row.get(name) or "").strip()
        if value:
            return value
    return ""


def normalize_history_url(url: str) -> Tuple[str, str, str]:
    raw = url.strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in ("http", "https") or parsed.hostname != "simu.howbuy.com":
        raise ValueError("Not a Howbuy private-fund URL: {}".format(url))

    parts = [part for part in parsed.path.split("/") if part]
    if parts and parts[-1].lower() == "lsjz":
        parts = parts[:-1]
    if len(parts) < 2:
        raise ValueError("Cannot identify product code from URL: {}".format(url))

    fund_id = parts[-1]
    product_path = "/{}/".format("/".join(parts))
    history_path = "/{}/lsjz".format("/".join(parts))
    authority = parsed.netloc
    product_url = urlunsplit(("https", authority, product_path, "", ""))
    history_url = urlunsplit(("https", authority, history_path, "", ""))
    return product_url, history_url, fund_id


def load_products(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            "Product list not found: {}. Copy products.example.csv to products.csv first.".format(
                path
            )
        )

    products: List[Dict[str, str]] = []
    seen = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Product list has no header row: {}".format(path))
        for line_number, row in enumerate(reader, start=2):
            name = first_value(row, NAME_COLUMNS)
            raw_url = first_value(row, URL_COLUMNS)
            if not name and not raw_url:
                continue
            try:
                product_url, history_url, fund_id = normalize_history_url(raw_url)
            except ValueError as exc:
                raise ValueError("Line {}: {}".format(line_number, exc)) from exc
            if history_url in seen:
                continue
            seen.add(history_url)
            products.append(
                {
                    "product_name": name,
                    "product_url": product_url,
                    "history_url": history_url,
                    "fund_id": fund_id,
                }
            )
    if not products:
        raise ValueError("No valid products found in {}".format(path))
    return products


def _header_index(headers: Sequence[str], patterns: Sequence[str]) -> Optional[int]:
    for index, header in enumerate(headers):
        normalized = re.sub(r"\s+", "", header)
        if any(pattern in normalized for pattern in patterns):
            return index
    return None


def normalize_date(value: str) -> str:
    match = DATE_RE.match(value.strip())
    if not match:
        raise ScrapeError("Invalid NAV date: {}".format(value))
    year, month, day = (int(part) for part in match.groups())
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError as exc:
        raise ScrapeError("Invalid NAV date: {}".format(value)) from exc


def normalize_nav(value: str, field: str) -> str:
    cleaned = value.strip().replace(",", "").replace("*", "")
    if not cleaned or cleaned == "--" or "登录可见" in cleaned:
        raise ScrapeError("{} is unavailable: {}".format(field, value))
    match = NUMBER_RE.search(cleaned)
    if not match:
        raise ScrapeError("Invalid {}: {}".format(field, value))
    number = match.group(0)
    try:
        Decimal(number)
    except InvalidOperation as exc:
        raise ScrapeError("Invalid {}: {}".format(field, value)) from exc
    return number


def parse_history_snapshot(snapshot: Dict[str, Any]) -> List[Dict[str, str]]:
    headers = [str(value) for value in snapshot.get("headers", [])]
    rows = snapshot.get("rows", [])
    if not headers or not isinstance(rows, list):
        raise ScrapeError("Historical NAV table has an unexpected structure")

    date_index = _header_index(headers, ("净值日期", "日期"))
    unit_index = _header_index(headers, ("单位净值", "净值/万份"))
    cumulative_index = _header_index(headers, ("累计净值",))
    change_index = _header_index(headers, ("涨跌幅", "增长率", "涨跌"))
    if date_index is None or unit_index is None or cumulative_index is None:
        raise ScrapeError("Required NAV columns were not found: {}".format(headers))

    parsed_rows: List[Dict[str, str]] = []
    minimum_width = max(date_index, unit_index, cumulative_index) + 1
    for raw in rows:
        if not isinstance(raw, list) or len(raw) < minimum_width:
            continue
        date_value = str(raw[date_index]).strip()
        if not DATE_RE.match(date_value):
            continue
        change = ""
        if change_index is not None and change_index < len(raw):
            change = str(raw[change_index]).strip()
        parsed_rows.append(
            {
                "date": normalize_date(date_value),
                "unit_nav": normalize_nav(str(raw[unit_index]), "unit NAV"),
                "cumulative_nav": normalize_nav(
                    str(raw[cumulative_index]), "cumulative NAV"
                ),
                "change_pct": change,
            }
        )
    if not parsed_rows:
        raise ScrapeError("No usable historical NAV rows were found")
    return parsed_rows


def cdp_evaluate(cdp: Any, expression: str) -> Any:
    """Evaluate directly through Chrome DevTools, without Playwright injection.

    Howbuy currently modifies JavaScript globals used by Playwright's injected
    selector/evaluation helpers. Direct CDP evaluation remains reliable.
    """
    result = cdp.send(
        "Runtime.evaluate",
        {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        },
    )
    if result.get("exceptionDetails"):
        details = result["exceptionDetails"]
        raise ScrapeError(
            "Chrome page evaluation failed: {}".format(
                details.get("text") or "unknown JavaScript error"
            )
        )
    return result.get("result", {}).get("value")


def cdp_evaluate_json(cdp: Any, function_source: str) -> Any:
    expression = "JSON.stringify(({})())".format(function_source)
    value = cdp_evaluate(cdp, expression)
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ScrapeError("Chrome returned invalid page data") from exc


def wait_for_snapshot(
    page: Any, cdp: Any, timeout_ms: int = 15_000
) -> Optional[Dict[str, Any]]:
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        snapshot = cdp_evaluate_json(cdp, EXTRACT_HISTORY_JS)
        if snapshot and snapshot.get("datedRows", 0) > 0:
            try:
                parse_history_snapshot(snapshot)
            except ScrapeError:
                pass
            else:
                return snapshot
        page.wait_for_timeout(400)
    return None


def open_history_page(
    page: Any, cdp: Any, history_url: str, headless: bool, login_timeout: int
) -> Dict[str, Any]:
    page.goto(history_url, wait_until="domcontentloaded", timeout=60_000)
    snapshot = wait_for_snapshot(page, cdp)
    if snapshot:
        return snapshot

    diagnostic = cdp_evaluate_json(cdp, DIAGNOSE_PAGE_JS)
    print("Howbuy page diagnostic:")
    print(json.dumps(diagnostic, ensure_ascii=False, indent=2))

    if headless:
        raise ScrapeError("Login expired or the historical NAV page is unavailable")

    print("\nHowbuy login, qualified-investor confirmation, or slider verification is required.")
    print("Complete it manually in the browser and open this exact history URL:")
    print(history_url)
    print("When the historical NAV table is visible, return here and press Enter.")
    try:
        input()
    except EOFError:
        print("Waiting up to {} seconds...".format(login_timeout))
        page.wait_for_timeout(login_timeout * 1000)

    snapshot = wait_for_snapshot(page, cdp, timeout_ms=30_000)
    if not snapshot:
        diagnostic = cdp_evaluate_json(cdp, DIAGNOSE_PAGE_JS)
        actual_url = diagnostic.get("url", "") if diagnostic else ""
        raise ScrapeError(
            "Historical NAV table is still unavailable after manual confirmation"
            + (" (current URL: {})".format(actual_url) if actual_url else "")
        )
    return snapshot


def page_signature(rows: Sequence[Dict[str, str]]) -> Tuple[str, str, int]:
    return rows[0]["date"], rows[-1]["date"], len(rows)


def advance_page(page: Any, cdp: Any, old_signature: Tuple[str, str, int]) -> bool:
    prepared = cdp_evaluate_json(cdp, PREPARE_NEXT_JS)
    if not prepared:
        return False
    try:
        clicked = cdp_evaluate(cdp, "({})()".format(CLICK_NEXT_JS))
    except Exception as exc:
        raise ScrapeError("Could not click the next-page control") from exc
    if not clicked:
        raise ScrapeError("Could not identify the next-page control")

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        page.wait_for_timeout(350)
        snapshot = cdp_evaluate_json(cdp, EXTRACT_HISTORY_JS)
        if not snapshot or snapshot.get("datedRows", 0) == 0:
            continue
        rows = parse_history_snapshot(snapshot)
        if page_signature(rows) != old_signature:
            return True
    return False


def fallback_product_name(page: Any, configured: str) -> str:
    if configured:
        return configured
    title = page.title() or ""
    return title.split(" - ", 1)[0].strip() or "Unknown product"


def scrape_product(
    page: Any,
    cdp: Any,
    product: Dict[str, str],
    headless: bool,
    login_timeout: int,
    max_pages: int,
) -> Tuple[str, List[Dict[str, str]], int]:
    snapshot = open_history_page(
        page, cdp, product["history_url"], headless, login_timeout
    )
    collected: Dict[str, Dict[str, str]] = {}
    seen_signatures = set()
    page_count = 0

    for _ in range(max_pages):
        rows = parse_history_snapshot(snapshot)
        signature = page_signature(rows)
        if signature in seen_signatures:
            break
        seen_signatures.add(signature)
        page_count += 1
        for row in rows:
            collected[row["date"]] = row

        if not advance_page(page, cdp, signature):
            break
        snapshot = cdp_evaluate_json(cdp, EXTRACT_HISTORY_JS)
        if not snapshot:
            raise ScrapeError("Historical NAV table disappeared after pagination")
    else:
        raise ScrapeError("Pagination exceeded {} pages".format(max_pages))

    ordered = sorted(collected.values(), key=lambda row: row["date"], reverse=True)
    if not ordered:
        raise ScrapeError("No historical NAV records were collected")
    return fallback_product_name(page, product["product_name"]), ordered, page_count


def load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"products": {}}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError("Cannot read progress file {}: {}".format(path, exc)) from exc
    if not isinstance(data, dict) or not isinstance(data.get("products", {}), dict):
        raise ValueError("Invalid progress file structure: {}".format(path))
    data.setdefault("products", {})
    return data


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def load_existing_rows(path: Path) -> Dict[Tuple[str, str], Dict[str, str]]:
    existing: Dict[Tuple[str, str], Dict[str, str]] = {}
    if not path.exists():
        return existing
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            history_url = (row.get("history_url") or "").strip()
            date = (row.get("date") or "").strip()
            if history_url and DATE_RE.match(date):
                existing[(history_url, date)] = {
                    field: row.get(field, "") for field in OUTPUT_FIELDS
                }
    return existing


def atomic_write_rows(path: Path, rows: Iterable[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    ordered = sorted(
        rows, key=lambda row: (row.get("product_name", ""), row.get("date", ""))
    )
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(ordered)
    temporary.replace(path)


def safe_filename_component(value: str) -> str:
    cleaned = INVALID_FILENAME_RE.sub("_", value.strip())
    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._- ")
    return cleaned or "未命名产品"


def product_output_path(
    output_dir: Path,
    product: Dict[str, str],
    product_name: str,
    rows: Sequence[Dict[str, str]],
) -> Path:
    if not rows:
        raise ScrapeError("Cannot name an output file without NAV rows")
    dates = sorted(row["date"] for row in rows)
    start = dates[0].replace("-", "")
    end = dates[-1].replace("-", "")
    filename = "{}-{}-{}-{}.csv".format(
        safe_filename_component(product["fund_id"]),
        safe_filename_component(product_name),
        start,
        end,
    )
    return output_dir / filename


def previous_output_path(
    output_dir: Path,
    product: Dict[str, str],
    state_entry: Dict[str, Any],
    allow_legacy: bool,
) -> Optional[Path]:
    saved = str(state_entry.get("output_file") or "").strip()
    if saved:
        candidate = Path(saved).expanduser()
        if not candidate.is_absolute():
            candidate = output_dir / candidate
        if candidate.is_file():
            return candidate.resolve()

    prefix = safe_filename_component(product["fund_id"]) + "-"
    matches = sorted(
        output_dir.glob(prefix + "*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if matches:
        return matches[0].resolve()

    legacy = output_dir / "net_values.csv"
    if allow_legacy and legacy.is_file():
        return legacy.resolve()
    return None


def scrape_with_retry(
    page: Any,
    cdp: Any,
    product: Dict[str, str],
    retries: int,
    headless: bool,
    login_timeout: int,
    max_pages: int,
) -> Tuple[str, List[Dict[str, str]], int]:
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 2):
        try:
            return scrape_product(
                page, cdp, product, headless, login_timeout, max_pages
            )
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            last_error = exc
            if attempt <= retries:
                print(
                    "  Attempt {}/{} failed: {}. Retrying...".format(
                        attempt, retries + 1, exc
                    )
                )
                page.wait_for_timeout(min(attempt * 1000, 5000))
    raise ScrapeError(str(last_error or "Unknown scrape failure"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch scrape authorized Howbuy historical NAV pages (/lsjz)."
    )
    parser.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--login-timeout", type=int, default=300)
    parser.add_argument("--max-pages", type=int, default=500)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--headless", action="store_true")
    return parser


def run(args: argparse.Namespace) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright is not installed. Run: python3 -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 2

    products = load_products(args.products.resolve())
    output_dir = args.output_dir.resolve()
    if args.output is not None:
        legacy_output = args.output.resolve()
        output_dir = legacy_output.parent if legacy_output.suffix else legacy_output
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = args.state.resolve()
    profile_path = args.profile.resolve()
    profile_path.mkdir(parents=True, exist_ok=True)
    state = load_state(state_path)
    succeeded = 0
    skipped = 0
    failed = 0
    output_files: List[Path] = []

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_path),
            channel="chrome",
            headless=args.headless,
            viewport={"width": 1470, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        cdp = context.new_cdp_session(page)
        try:
            for index, product in enumerate(products, start=1):
                history_url = product["history_url"]
                previous = state["products"].get(history_url, {})
                existing_path = previous_output_path(
                    output_dir, product, previous, allow_legacy=len(products) == 1
                )
                existing = (
                    load_existing_rows(existing_path) if existing_path else {}
                )
                has_rows = any(key[0] == history_url for key in existing)
                if (
                    not args.refresh
                    and previous.get("status") == "completed"
                    and has_rows
                ):
                    print(
                        "[{}/{}] Skip completed: {}".format(
                            index,
                            len(products),
                            product["product_name"] or history_url,
                        )
                    )
                    if existing_path:
                        output_files.append(existing_path)
                    skipped += 1
                    continue

                print(
                    "[{}/{}] Scraping: {}".format(
                        index, len(products), product["product_name"] or history_url
                    )
                )
                started_at = datetime.now().astimezone().isoformat(timespec="seconds")
                try:
                    name, nav_rows, page_count = scrape_with_retry(
                        page,
                        cdp,
                        product,
                        args.retries,
                        args.headless,
                        args.login_timeout,
                        args.max_pages,
                    )
                    scraped_at = datetime.now().astimezone().isoformat(
                        timespec="seconds"
                    )
                    for nav in nav_rows:
                        output_row = {
                            "product_name": name,
                            "product_url": product["product_url"],
                            "history_url": history_url,
                            "fund_id": product["fund_id"],
                            "date": nav["date"],
                            "unit_nav": nav["unit_nav"],
                            "cumulative_nav": nav["cumulative_nav"],
                            "change_pct": nav["change_pct"],
                            "scraped_at": scraped_at,
                        }
                        existing[(history_url, nav["date"])] = output_row
                    product_rows = [
                        row
                        for (row_url, _), row in existing.items()
                        if row_url == history_url
                    ]
                    output_path = product_output_path(
                        output_dir, product, name, product_rows
                    ).resolve()
                    if existing_path and existing_path != output_path:
                        if output_path.exists():
                            raise ScrapeError(
                                "Refusing to overwrite existing output: {}".format(
                                    output_path
                                )
                            )
                        existing_path.rename(output_path)
                    atomic_write_rows(output_path, product_rows)
                    state["products"][history_url] = {
                        "status": "completed",
                        "product_name": name,
                        "started_at": started_at,
                        "finished_at": scraped_at,
                        "record_count": len(nav_rows),
                        "page_count": page_count,
                        "first_date": nav_rows[-1]["date"],
                        "last_date": nav_rows[0]["date"],
                        "output_file": output_path.name,
                    }
                    atomic_write_json(state_path, state)
                    output_files.append(output_path)
                    succeeded += 1
                    print(
                        "  Saved {} rows from {} pages ({} to {}).".format(
                            len(nav_rows),
                            page_count,
                            nav_rows[-1]["date"],
                            nav_rows[0]["date"],
                        )
                    )
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception as exc:
                    failed += 1
                    state["products"][history_url] = {
                        "status": "failed",
                        "product_name": product["product_name"],
                        "started_at": started_at,
                        "finished_at": datetime.now()
                        .astimezone()
                        .isoformat(timespec="seconds"),
                        "error": str(exc),
                    }
                    atomic_write_json(state_path, state)
                    print("  Failed: {}".format(exc), file=sys.stderr)
                if index < len(products) and args.delay > 0:
                    time.sleep(args.delay)
        finally:
            context.close()

    print(
        "Finished: {} succeeded, {} skipped, {} failed. Output directory: {}".format(
            succeeded, skipped, failed, output_dir
        )
    )
    for output_file in sorted(set(output_files)):
        print("  {}".format(output_file))
    return 1 if failed else 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if (
        args.delay < 0
        or args.retries < 0
        or args.login_timeout <= 0
        or args.max_pages <= 0
    ):
        parser.error(
            "delay/retries must be non-negative; login-timeout/max-pages must be positive"
        )
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
