"""Cache V2A style-index daily NAVs from the CSIndex official API.

The report generator never calls this script or the network.  This updater is
the only writer for ``style_index_nav.json`` and is safe to rerun: it bridges
from the last saved close and appends only newer observations.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "weekly_report.yaml"
CSINDEX_API = "https://www.csindex.com.cn/csindex-home/perf/index-perf"
DEFAULT_START_DATE = "20251231"


def parse_args():
    parser = argparse.ArgumentParser(description="Update cached V2A style-index daily NAVs")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--output", type=Path,
        help="Output path; defaults to style.data_path in the report config")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE, help="Initial YYYYMMDD date")
    parser.add_argument("--end-date", help="Final YYYYMMDD date; default is today")
    parser.add_argument(
        "--allow-partial", action="store_true",
        help="Keep fresh validated cached fallbacks for failed indices")
    return parser.parse_args()


def _valid_compact_date(value: str, label: str) -> str:
    try:
        datetime.strptime(value, "%Y%m%d")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be YYYYMMDD") from exc
    return value


def _canonical_index_code(value: Any) -> str:
    code = str(value).strip().upper()
    return code.zfill(6) if code.isdigit() else code


def _load_style_config(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"Cannot read config {path}: {exc}") from exc
    try:
        style = raw["style"]
        indices = style["indices"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("Config is missing style.indices") from exc
    if not isinstance(indices, dict) or not indices:
        raise RuntimeError("style.indices must be a non-empty mapping")
    result = {}
    for key, details in indices.items():
        if not isinstance(details, dict):
            raise RuntimeError(f"style.indices.{key} must be a mapping")
        for field in ("label", "source_key", "wind_code", "csindex_code"):
            if not isinstance(details.get(field), str) or not details[field]:
                raise RuntimeError(f"style.indices.{key}.{field} must be a non-empty string")
        result[key] = {
            "label": details["label"],
            "source_key": details["source_key"],
            "wind_code": details["wind_code"],
            "csindex_code": details["csindex_code"],
        }
    data_path = style.get("data_path")
    if not isinstance(data_path, str) or not data_path:
        raise RuntimeError("style.data_path must be a non-empty string")
    max_staleness_days = style.get("max_staleness_days")
    if (isinstance(max_staleness_days, bool) or
            not isinstance(max_staleness_days, int) or max_staleness_days < 0):
        raise RuntimeError("style.max_staleness_days must be a non-negative integer")
    return {
        "indices": result,
        "data_path": data_path,
        "max_staleness_days": max_staleness_days,
    }


def _load_existing(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read style cache {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("Style cache top level must be an object")
    return raw


def fetch_index_data(index_code: str, start_date: str, end_date: str) -> dict[str, float]:
    """Fetch official daily closes as ``{YYYYMMDD: close}``."""
    url = f"{CSINDEX_API}?indexCode={index_code}&startDate={start_date}&endDate={end_date}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    if payload.get("code") != "200":
        raise RuntimeError("API returned code={}, msg={}".format(
            payload.get("code"), payload.get("msg")))
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise RuntimeError("API returned no data list")
    result = {}
    reported_codes = set()
    for row in rows:
        try:
            item_date = str(row["tradeDate"])
            close = float(row["close"])
            _valid_compact_date(item_date, "CSIndex tradeDate")
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("API returned invalid observation") from exc
        if close <= 0:
            raise RuntimeError(f"API returned non-positive close on {item_date}")
        reported_code = row.get("indexCode")
        if reported_code is not None:
            reported_codes.add(_canonical_index_code(reported_code))
        result[item_date] = close
    if reported_codes and reported_codes != {_canonical_index_code(index_code)}:
        raise RuntimeError(
            f"API returned index code(s) {sorted(reported_codes)}, expected {index_code}")
    if not result:
        raise RuntimeError("API returned an empty series")
    return result


def _normalize_initial(data: dict[str, float]) -> dict[str, Any]:
    first_date = min(data)
    base_close = data[first_date]
    dates = sorted(data)
    return {
        "dates": dates,
        "navs": [round(data[item_date] / base_close, 10) for item_date in dates],
    }


def _extend(existing: dict[str, Any], fresh: dict[str, float]) -> dict[str, Any]:
    dates = existing.get("dates")
    navs = existing.get("navs")
    if not isinstance(dates, list) or not isinstance(navs, list) or len(dates) != len(navs) or not dates:
        raise RuntimeError("Existing series has invalid dates/navs")
    bridge_date = dates[-1]
    bridge_nav = float(navs[-1])
    if bridge_date not in fresh:
        raise RuntimeError(f"API response lacks bridge date {bridge_date}")
    bridge_close = fresh[bridge_date]
    extended_dates = list(dates)
    extended_navs = list(navs)
    for item_date in sorted(fresh):
        if item_date <= bridge_date:
            continue
        extended_dates.append(item_date)
        extended_navs.append(round(bridge_nav * fresh[item_date] / bridge_close, 10))
    return {"dates": extended_dates, "navs": extended_navs}


def _validate_series_identity(
        source_key: str, series: dict[str, Any], details: dict[str, str]) -> None:
    for field in ("label", "wind_code", "csindex_code"):
        actual = series.get(field)
        expected = details[field]
        if actual != expected:
            raise RuntimeError(
                f"Cached source {source_key} has mismatched {field}: "
                f"expected {expected!r}, got {actual!r}")


def _validate_output_cache(
        payload: dict[str, Any], indices: dict[str, dict[str, str]], end_date: str,
        max_staleness_days: int) -> None:
    target = datetime.strptime(end_date, "%Y%m%d").date()
    for details in indices.values():
        source_key = details["source_key"]
        series = payload.get(source_key)
        if not isinstance(series, dict):
            raise RuntimeError(f"Output cache is missing source {source_key}")
        _validate_series_identity(source_key, series, details)
        dates = series.get("dates")
        navs = series.get("navs")
        if (not isinstance(dates, list) or not isinstance(navs, list) or not dates or
                len(dates) != len(navs) or dates != sorted(dates) or
                len(dates) != len(set(dates))):
            raise RuntimeError(f"Output source {source_key} has invalid dates/navs")
        latest = datetime.strptime(dates[-1], "%Y%m%d").date()
        lag_days = (target - latest).days
        if lag_days < 0:
            raise RuntimeError(f"Output source {source_key} contains a future observation")
        if lag_days > max_staleness_days:
            raise RuntimeError(
                f"Output source {source_key} is stale by {lag_days} days "
                f"(limit {max_staleness_days})")


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def main() -> int:
    args = parse_args()
    try:
        start_date = _valid_compact_date(args.start_date, "--start-date")
        end_date = _valid_compact_date(
            args.end_date or date.today().strftime("%Y%m%d"), "--end-date")
        if end_date < start_date:
            raise ValueError("--end-date must not precede --start-date")
        style_config = _load_style_config(args.config)
        indices = style_config["indices"]
        output_path = args.output or Path(style_config["data_path"])
        if not output_path.is_absolute():
            output_path = PROJECT_ROOT / output_path
        existing = _load_existing(output_path)
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2

    updated = dict(existing)
    updated["_metadata"] = {
        "source": "CSIndex official API",
        "wind_code_reference": "config/weekly_report.yaml style.indices",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    failures = []
    for key, details in indices.items():
        source_key = details["source_key"]
        current = existing.get(source_key)
        request_start = start_date
        if isinstance(current, dict) and current.get("dates"):
            request_start = str(current["dates"][-1])
        try:
            if isinstance(current, dict):
                _validate_series_identity(source_key, current, details)
            fresh = fetch_index_data(details["csindex_code"], request_start, end_date)
            if isinstance(current, dict) and current.get("dates"):
                series = _extend(current, fresh)
            else:
                series = _normalize_initial(fresh)
            series.update({
                "label": details["label"],
                "wind_code": details["wind_code"],
                "csindex_code": details["csindex_code"],
            })
            updated[source_key] = series
            print("{}: {} dates ({} → {})".format(
                key, len(series["dates"]), series["dates"][0], series["dates"][-1]))
        except Exception as exc:
            failures.append("{} ({}): {}".format(key, details["csindex_code"], exc))
            print(f"WARN: {failures[-1]}")

    if failures and not args.allow_partial:
        print("Failed indices: {}".format("; ".join(failures)))
        print(f"Style cache unchanged: {output_path}")
        return 2
    try:
        _validate_output_cache(
            updated, indices, end_date, style_config["max_staleness_days"])
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: output cache validation failed: {exc}")
        print(f"Style cache unchanged: {output_path}")
        return 2
    _write_json_atomic(output_path, updated)
    print(f"Saved style cache: {output_path}")
    if failures:
        print("Used cached fallbacks for: {}".format("; ".join(failures)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
