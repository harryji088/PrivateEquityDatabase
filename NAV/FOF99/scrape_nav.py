#!/usr/bin/env python3
"""Batch scrape historical NAV data from authorized FOF99 product pages."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PRODUCTS = SCRIPT_DIR / "products.csv"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR.parent / "output"
DEFAULT_STATE = SCRIPT_DIR / "state" / "progress.json"
DEFAULT_PROFILE = Path.home() / ".config" / "fof99-browser-profile"

SCROLLER_SELECTOR = ".virtual-content"
ROW_SELECTOR = ".flex.flex-nowrap.border-b-ebeef5.justify-around"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
INVALID_FILENAME_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
REGISTRATION_RE = re.compile(
    r"备案编号[^\n:：]{0,30}[:：]\s*([A-Za-z0-9_-]+)", re.IGNORECASE
)

OUTPUT_FIELDS = [
    "product_name",
    "product_code",
    "product_url",
    "date",
    "unit_nav",
    "cumulative_nav",
    "adjusted_nav",
    "change_pct",
    "scraped_at",
]

NAME_COLUMNS = ("product_name", "name", "产品名称", "产品名")
URL_COLUMNS = ("product_url", "url", "产品地址", "网页地址", "链接")


class ScrapeError(RuntimeError):
    """Raised when a product page cannot be scraped reliably."""


def clean_text(value: Optional[str]) -> str:
    """Remove whitespace inserted between SVG-rendered digits."""

    return "".join((value or "").split())


def parse_nav_cells(cells: Sequence[Optional[str]]) -> Optional[Dict[str, str]]:
    """Convert the five visible NAV cells into a normalized record."""

    values = [clean_text(value) for value in cells]
    if len(values) < 5 or not DATE_RE.match(values[0]):
        return None
    return {
        "date": values[0],
        "unit_nav": values[1],
        "cumulative_nav": values[2],
        "adjusted_nav": values[3],
        "change_pct": values[4],
    }


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
            if not name and not url:
                continue
            if not url.startswith("https://mp.fof99.com/fund/view/"):
                raise ValueError(
                    "Invalid FOF99 product URL on line {}: {}".format(line_number, url)
                )
            if url in seen_urls:
                continue
            seen_urls.add(url)
            product_code = url.rstrip("/").rsplit("/", 1)[-1]
            products.append(
                {
                    "product_name": name,
                    "product_code": product_code,
                    "product_url": url,
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
    product: Dict[str, str],
    product_name: str,
    rows: Sequence[Dict[str, str]],
) -> Path:
    if not rows:
        raise ScrapeError("Cannot name an output file without NAV rows")
    dates = sorted(row["date"] for row in rows)
    filename = "{}-{}-{}-{}.csv".format(
        safe_filename_component(product["product_code"]),
        safe_filename_component(product_name),
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

    prefix = safe_filename_component(product["product_code"]) + "-"
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


def find_nav_scroller(page: Any) -> Any:
    candidates = page.locator(SCROLLER_SELECTOR).all()
    for candidate in candidates:
        if candidate.locator(ROW_SELECTOR).count() > 0:
            return candidate
    raise ScrapeError("NAV virtual list was not found on the product page")


def wait_for_product_page(page: Any, url: str, login_timeout: int) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    try:
        page.wait_for_selector(
            "{} {}".format(SCROLLER_SELECTOR, ROW_SELECTOR), timeout=12_000
        )
        return
    except Exception:
        print("\nThe NAV list is not visible. Complete login in the opened browser.")
        print("Waiting up to {} seconds for the product page...".format(login_timeout))

    try:
        page.wait_for_selector(
            "{} {}".format(SCROLLER_SELECTOR, ROW_SELECTOR),
            timeout=login_timeout * 1000,
        )
    except Exception as exc:
        raise ScrapeError(
            "Login timed out or the account cannot access this product"
        ) from exc


def scrape_visible_rows(scroller: Any) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    for row in scroller.locator(ROW_SELECTOR).all():
        cells = row.locator(":scope > div").all_text_contents()
        parsed = parse_nav_cells(cells)
        if parsed:
            records.append(parsed)
    return records


def scrape_product(page: Any, url: str, login_timeout: int) -> List[Dict[str, str]]:
    wait_for_product_page(page, url, login_timeout)
    scroller = find_nav_scroller(page)
    scroller.evaluate("el => { el.scrollTop = 0; }")
    page.wait_for_timeout(200)

    records: Dict[str, Dict[str, str]] = {}
    unchanged_rounds = 0
    previous_top = -1

    while True:
        for record in scrape_visible_rows(scroller):
            records[record["date"]] = record

        metrics = scroller.evaluate(
            """el => ({
                top: el.scrollTop,
                clientHeight: el.clientHeight,
                scrollHeight: el.scrollHeight
            })"""
        )
        top = int(metrics["top"])
        client_height = int(metrics["clientHeight"])
        scroll_height = int(metrics["scrollHeight"])

        if top + client_height >= scroll_height - 2:
            break

        next_top = min(
            top + max(int(client_height * 0.75), 84),
            scroll_height - client_height,
        )
        scroller.evaluate("(el, value) => { el.scrollTop = value; }", next_top)
        page.wait_for_timeout(220)

        if next_top == previous_top:
            unchanged_rounds += 1
            if unchanged_rounds >= 3:
                raise ScrapeError("NAV list stopped scrolling before reaching the bottom")
        else:
            unchanged_rounds = 0
        previous_top = next_top

    page.wait_for_timeout(150)
    for record in scrape_visible_rows(scroller):
        records[record["date"]] = record

    if not records:
        raise ScrapeError("No NAV records were extracted")

    row_height = scroller.locator(ROW_SELECTOR).first.evaluate(
        "el => el.getBoundingClientRect().height"
    )
    if row_height:
        expected = int(round(scroll_height / float(row_height)))
        if expected >= 10 and len(records) < int(expected * 0.9):
            raise ScrapeError(
                "Only {} of about {} NAV rows were captured".format(len(records), expected)
            )

    return sorted(records.values(), key=lambda row: row["date"])


def page_product_name(page: Any, fallback: str) -> str:
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


def scrape_with_retry(
    page: Any,
    product: Dict[str, str],
    retries: int,
    login_timeout: int,
) -> Tuple[str, List[Dict[str, str]]]:
    last_error: Optional[BaseException] = None
    for attempt in range(1, retries + 2):
        try:
            rows = scrape_product(page, product["product_url"], login_timeout)
            return page_product_name(page, product["product_name"]), rows
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
        description="Batch scrape historical NAV data from authorized FOF99 pages."
    )
    parser.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--login-timeout", type=int, default=300)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-scrape products already marked complete in the progress file.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without a visible browser; use only after a login profile exists.",
    )
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
            viewport={"width": 1440, "height": 900},
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
                        page, product["product_code"]
                    )
                    output_product = dict(product)
                    output_product["product_code"] = registration_code
                    scraped_at = datetime.now().astimezone().isoformat(timespec="seconds")
                    for row in nav_rows:
                        output_row = {
                            "product_name": name,
                            "product_code": registration_code,
                            "product_url": url,
                            "date": row["date"],
                            "unit_nav": row["unit_nav"],
                            "cumulative_nav": row["cumulative_nav"],
                            "adjusted_nav": row["adjusted_nav"],
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
                        output_dir, output_product, name, product_rows
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
                        "first_date": nav_rows[0]["date"],
                        "last_date": nav_rows[-1]["date"],
                        "output_file": output_path.name,
                    }
                    atomic_write_json(state_path, state)
                    output_files.append(output_path)
                    succeeded += 1
                    print(
                        "  Saved {} rows ({} to {}).".format(
                            len(nav_rows), nav_rows[0]["date"], nav_rows[-1]["date"]
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
