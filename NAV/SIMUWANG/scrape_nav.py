#!/usr/bin/env python3
"""Batch scrape historical NAV data from authorized Simuwang product pages."""

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

from nav_decoder import DecodeError, decode_nav_rows, latest_nav_from_return


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PRODUCTS = SCRIPT_DIR / "products.csv"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR.parent / "output"
DEFAULT_STATE = SCRIPT_DIR / "state" / "progress.json"
DEFAULT_PROFILE = Path.home() / ".config" / "simuwang-browser-profile"

URL_RE = re.compile(
    r"^https://dc\.simuwang\.com/product/([A-Za-z0-9]+)\.html(?:\?.*)?$"
)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RETURN_RE = re.compile(
    r"成立(?:以来|来)收益.{0,80}?([+-]?\d+(?:\.\d+)?)%", re.DOTALL
)
REGISTRATION_RE = re.compile(
    r"备案(?:编号|编码)\s*[：:]\s*([A-Za-z0-9_-]+)", re.IGNORECASE
)
INVALID_FILENAME_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

OUTPUT_FIELDS = [
    "product_name",
    "product_code",
    "product_url",
    "fund_id",
    "date",
    "unit_nav",
    "cumulative_nav_reinvest",
    "cumulative_nav_no_reinvest",
    "change_pct",
    "scraped_at",
]

NAME_COLUMNS = ("product_name", "name", "产品名称", "产品名")
URL_COLUMNS = ("product_url", "url", "产品地址", "网页地址", "链接")
LATEST_NAV_COLUMNS = (
    "latest_cumulative_nav",
    "latest_nav",
    "最新累计净值",
    "最新复权净值",
)

EXTRACT_ROWS_JS = r"""
() => {
  const bodies = [...document.querySelectorAll('table.el-table__body')];
  const body = bodies.find(table => {
    const row = table.querySelector('tbody tr');
    const cells = row ? [...row.querySelectorAll(':scope > td')] : [];
    return cells.length === 6 && cells[1]?.querySelector('img');
  });
  if (!body) return [];
  return [...body.querySelectorAll('tbody tr')].map(row => {
    const cells = [...row.querySelectorAll(':scope > td')];
    const navCells = [1, 2, 4].map(index => {
      const cellRect = cells[index].getBoundingClientRect();
      return [...cells[index].querySelectorAll('img')]
        .filter(img => {
          const rect = img.getBoundingClientRect();
          return rect.width > 1 && rect.height > 1 &&
            rect.right > cellRect.left && rect.left < cellRect.right &&
            rect.bottom > cellRect.top && rect.top < cellRect.bottom;
        })
        .map(img => img.src);
    });
    return {
      date: cells[0]?.textContent?.trim() || '',
      nav_cells: navCells,
      change_pct: cells[5]?.textContent?.trim() || ''
    };
  }).filter(row => /^\d{4}-\d{2}-\d{2}$/.test(row.date));
}
"""


class ScrapeError(RuntimeError):
    """Raised when a product page cannot be scraped reliably."""


def first_value(row: Dict[str, str], names: Iterable[str]) -> str:
    for name in names:
        value = (row.get(name) or "").strip()
        if value:
            return value
    return ""


def load_products(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            "Product list not found: {}. Copy products.example.csv to products.csv first.".format(
                path
            )
        )
    products: List[Dict[str, str]] = []
    seen_urls = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Product list has no header row: {}".format(path))
        for line_number, row in enumerate(reader, start=2):
            name = first_value(row, NAME_COLUMNS)
            url = first_value(row, URL_COLUMNS)
            latest_nav = first_value(row, LATEST_NAV_COLUMNS)
            match = URL_RE.match(url)
            if not name and not url:
                continue
            if not match:
                raise ValueError(
                    "Invalid Simuwang product URL on line {}: {}".format(
                        line_number, url
                    )
                )
            if latest_nav:
                try:
                    Decimal(latest_nav)
                except InvalidOperation as exc:
                    raise ValueError(
                        "Invalid latest cumulative NAV on line {}: {}".format(
                            line_number, latest_nav
                        )
                    ) from exc
            if url in seen_urls:
                continue
            seen_urls.add(url)
            products.append(
                {
                    "product_name": name,
                    "product_url": url,
                    "fund_id": match.group(1),
                    "latest_cumulative_nav": latest_nav,
                }
            )
    if not products:
        raise ValueError("No valid products found in {}".format(path))
    return products


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
    rows: Dict[Tuple[str, str], Dict[str, str]] = {}
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            url = (row.get("product_url") or "").strip()
            date = (row.get("date") or "").strip()
            if url and DATE_RE.match(date):
                rows[(url, date)] = {field: row.get(field, "") for field in OUTPUT_FIELDS}
    return rows


def atomic_write_rows(path: Path, rows: Iterable[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    ordered = sorted(
        rows,
        key=lambda row: (row.get("product_name", ""), row.get("date", "")),
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
    product_code: str,
    product_name_value: str,
    rows: Sequence[Dict[str, str]],
) -> Path:
    if not rows:
        raise ScrapeError("Cannot name an output file without NAV rows")
    dates = sorted(row["date"] for row in rows)
    filename = "{}-{}-{}-{}.csv".format(
        safe_filename_component(product_code),
        safe_filename_component(product_name_value),
        dates[0].replace("-", ""),
        dates[-1].replace("-", ""),
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

    registration_code = str(state_entry.get("registration_code") or "").strip()
    prefixes = [registration_code, product["fund_id"]]
    for value in prefixes:
        if not value:
            continue
        matches = sorted(
            output_dir.glob(safe_filename_component(value) + "-*.csv"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if matches:
            return matches[0].resolve()

    legacy = output_dir / "net_values.csv"
    if allow_legacy and legacy.is_file():
        return legacy.resolve()
    return None


def find_history_table(page: Any) -> Any:
    for body in page.locator("table.el-table__body").all():
        rows = body.locator("tbody tr")
        if rows.count() == 0:
            continue
        cells = rows.first.locator(":scope > td")
        if cells.count() == 6 and cells.nth(1).locator("img").count() > 0:
            return body
    raise ScrapeError("Historical NAV table was not found")


def wait_for_product_page(page: Any, url: str, login_timeout: int) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    tab = page.locator("h2.xp-nav-item").filter(has_text="历史净值/分红").first

    def ready() -> bool:
        try:
            return tab.is_visible() and page.locator(".xs-pc-login:visible").count() == 0
        except Exception:
            return False

    initial_deadline = time.monotonic() + 15
    while time.monotonic() < initial_deadline:
        if ready():
            return
        page.wait_for_timeout(300)

    print("\nComplete login, CAPTCHA, or risk acknowledgement in the browser.")
    print("Waiting up to {} seconds...".format(login_timeout))
    deadline = time.monotonic() + login_timeout
    while time.monotonic() < deadline:
        if ready():
            return
        page.wait_for_timeout(500)
    raise ScrapeError("Login timed out or this product is not accessible")


def open_history_table(page: Any, login_timeout: int) -> Any:
    tab = page.locator("h2.xp-nav-item").filter(has_text="历史净值/分红").first
    prompted = False
    deadline = time.monotonic() + login_timeout
    while time.monotonic() < deadline:
        if page.locator(".xs-pc-login:visible").count() > 0:
            if not prompted:
                print("\nComplete login or investor verification in the browser.")
                print("The scraper will continue automatically after the overlay closes.")
                prompted = True
            page.wait_for_timeout(500)
            continue

        try:
            tab.click(timeout=10_000)
        except Exception:
            page.wait_for_timeout(500)
            continue

        table_deadline = min(deadline, time.monotonic() + 30)
        while time.monotonic() < table_deadline:
            if page.locator(".xs-pc-login:visible").count() > 0:
                break
            try:
                return find_history_table(page)
            except ScrapeError:
                page.wait_for_timeout(500)
    raise ScrapeError("Historical NAV table did not load")


def load_all_history(page: Any, table: Any, max_rounds: int = 120) -> int:
    section = table.locator("xpath=ancestor::section[1]")
    stable_rounds = 0
    last_count = table.locator("tbody tr").count()

    for _ in range(max_rounds):
        markers = section.get_by_text("加载中", exact=True)
        if markers.count() == 0:
            break
        marker = markers.first
        try:
            marker.scroll_into_view_if_needed(timeout=10_000)
        except Exception:
            page.mouse.wheel(0, 500)
        page.wait_for_timeout(750)
        current_count = table.locator("tbody tr").count()
        if current_count > last_count:
            stable_rounds = 0
            last_count = current_count
        else:
            stable_rounds += 1
            if stable_rounds >= 16:
                break
            page.mouse.wheel(0, 350)

    return table.locator("tbody tr").count()


def extract_latest_nav(page: Any, override: str) -> Decimal:
    if override:
        return Decimal(override)
    body_text = page.locator("body").inner_text(timeout=30_000)
    match = RETURN_RE.search(body_text)
    if not match:
        raise ScrapeError(
            "Could not infer latest cumulative NAV. Add latest_cumulative_nav to products.csv."
        )
    return latest_nav_from_return(match.group(1))


def product_name(page: Any, fallback: str) -> str:
    if fallback:
        return fallback
    title = page.title() or ""
    return title.split("_", 1)[0].strip() or "Unknown product"


def extract_registration_code(text: str) -> str:
    match = REGISTRATION_RE.search(text or "")
    return match.group(1).strip() if match else ""


def page_registration_code(page: Any, fallback: str) -> str:
    try:
        body_text = page.locator("body").inner_text(timeout=10_000)
    except Exception:
        return fallback
    return extract_registration_code(body_text) or fallback


def scrape_product(
    page: Any, product: Dict[str, str], login_timeout: int
) -> Tuple[str, List[Dict[str, str]]]:
    wait_for_product_page(page, product["product_url"], login_timeout)
    table = open_history_table(page, login_timeout)
    row_count = load_all_history(page, table)
    if row_count < 2:
        raise ScrapeError("Too few historical NAV rows were loaded")

    latest_nav = extract_latest_nav(page, product["latest_cumulative_nav"])
    raw_rows = page.evaluate(EXTRACT_ROWS_JS)
    if len(raw_rows) != row_count:
        raise ScrapeError(
            "Extracted {} of {} loaded rows".format(len(raw_rows), row_count)
        )
    try:
        decoded = decode_nav_rows(raw_rows, latest_nav)
    except DecodeError as exc:
        raise ScrapeError(str(exc)) from exc
    return product_name(page, product["product_name"]), decoded


def scrape_with_retry(
    page: Any,
    product: Dict[str, str],
    retries: int,
    login_timeout: int,
) -> Tuple[str, List[Dict[str, str]]]:
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 2):
        try:
            return scrape_product(page, product, login_timeout)
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
                page.wait_for_timeout(min(1000 * attempt, 5000))
    raise ScrapeError(str(last_error or "Unknown scrape failure"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch scrape historical NAV data from authorized Simuwang pages."
    )
    parser.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--login-timeout", type=int, default=300)
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
    total = len(products)
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
        try:
            for index, product in enumerate(products, start=1):
                url = product["product_url"]
                previous = state["products"].get(url, {})
                existing_path = previous_output_path(
                    output_dir, product, previous, allow_legacy=total == 1
                )
                existing = (
                    load_existing_rows(existing_path) if existing_path else {}
                )
                has_existing_rows = any(key[0] == url for key in existing)
                if (
                    not args.refresh
                    and previous.get("status") == "completed"
                    and has_existing_rows
                ):
                    print(
                        "[{}/{}] Skip completed: {}".format(
                            index, total, product["product_name"] or url
                        )
                    )
                    if existing_path:
                        output_files.append(existing_path)
                    skipped += 1
                    continue

                print(
                    "[{}/{}] Scraping: {}".format(
                        index, total, product["product_name"] or url
                    )
                )
                started_at = datetime.now().astimezone().isoformat(timespec="seconds")
                try:
                    name, nav_rows = scrape_with_retry(
                        page, product, args.retries, args.login_timeout
                    )
                    registration_code = page_registration_code(
                        page, product["fund_id"]
                    )
                    scraped_at = datetime.now().astimezone().isoformat(timespec="seconds")
                    for row in nav_rows:
                        output_row = {
                            "product_name": name,
                            "product_code": registration_code,
                            "product_url": url,
                            "fund_id": product["fund_id"],
                            "date": row["date"],
                            "unit_nav": row["unit_nav"],
                            "cumulative_nav_reinvest": row[
                                "cumulative_nav_reinvest"
                            ],
                            "cumulative_nav_no_reinvest": row[
                                "cumulative_nav_no_reinvest"
                            ],
                            "change_pct": row["change_pct"],
                            "scraped_at": scraped_at,
                        }
                        existing[(url, row["date"])] = output_row
                    product_rows = [
                        row
                        for (row_url, _), row in existing.items()
                        if row_url == url
                    ]
                    output_path = product_output_path(
                        output_dir, registration_code, name, product_rows
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
                    state["products"][url] = {
                        "status": "completed",
                        "product_name": name,
                        "registration_code": registration_code,
                        "started_at": started_at,
                        "finished_at": scraped_at,
                        "record_count": len(nav_rows),
                        "first_date": nav_rows[-1]["date"],
                        "last_date": nav_rows[0]["date"],
                        "output_file": output_path.name,
                    }
                    atomic_write_json(state_path, state)
                    output_files.append(output_path)
                    succeeded += 1
                    print(
                        "  Saved {} rows ({} to {}).".format(
                            len(nav_rows), nav_rows[-1]["date"], nav_rows[0]["date"]
                        )
                    )
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception as exc:
                    failed += 1
                    state["products"][url] = {
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
                if index < total and args.delay > 0:
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
    if args.delay < 0 or args.retries < 0 or args.login_timeout <= 0:
        parser.error("delay/retries must be non-negative and login-timeout must be positive")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
