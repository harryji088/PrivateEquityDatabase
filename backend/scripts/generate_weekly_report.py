"""Generate a deterministic weekly report from existing local data only.

Run from the repository root or ``backend`` directory.  The script opens SQLite
in read-only mode and does not make network requests.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from analytics.alpha_heatmap import analyze_alpha_heatmap
from analytics.anomaly_detection import detect_anomalies
from analytics.benchmark_analysis import analyze_benchmarks
from analytics.data_access import (
    available_dates,
    load_benchmark_nav,
    load_observations,
    load_style_nav,
    open_read_only_database,
)
from analytics.facts_builder import build_facts, write_json_atomic, write_text_atomic
from analytics.manager_analysis import build_focus_manager_cards
from analytics.report_renderer import render_report
from analytics.schemas import AnalyticsError, load_focus_config, load_report_config
from analytics.size_analysis import analyze_size_groups
from analytics.style_analysis import analyze_style_proxies
from analytics.universe_analysis import analyze_universe


def parse_args():
    parser = argparse.ArgumentParser(description="Generate the offline quant weekly report")
    parser.add_argument("--as-of", help="Report date in YYYY-MM-DD; default is the latest database week")
    parser.add_argument("--db", type=Path, default=PROJECT_ROOT / "cc_data.sqlite3")
    parser.add_argument("--benchmark", type=Path, default=PROJECT_ROOT / "benchmark_nav.json")
    parser.add_argument(
        "--style", type=Path,
        help="Style cache path; defaults to style.data_path in the report config")
    parser.add_argument("--focus-config", type=Path, default=PROJECT_ROOT / "config" / "focus_managers.yaml")
    parser.add_argument("--report-config", type=Path, default=PROJECT_ROOT / "config" / "weekly_report.yaml")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--facts-dir", type=Path, default=None)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--print-summary", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="Replace artifacts for an existing report date")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report_config = load_report_config(args.report_config)
        focus_config = load_focus_config(args.focus_config)
        style_path = args.style or _project_path(report_config["style"]["data_path"])
        connection = open_read_only_database(args.db)
        try:
            observations = load_observations(connection, report_config["strategies"])
        finally:
            connection.close()
        all_report_dates = available_dates(observations)
        as_of_date = args.as_of or all_report_dates[-1]
        if as_of_date not in all_report_dates:
            raise AnalyticsError("No configured-strategy data for {}. Latest available dates: {}".format(
                as_of_date, ", ".join(all_report_dates[-3:])))
        observations = [
            item for item in observations if item.as_of_date.isoformat() <= as_of_date
        ]
        report_dates = [item for item in all_report_dates if item <= as_of_date]
        index = report_dates.index(as_of_date)
        previous_as_of_date = report_dates[index - 1] if index else None
        benchmark_data = load_benchmark_nav(args.benchmark, report_config["benchmarks"])
        style_data = load_style_nav(style_path, report_config["style"]["indices"])
        benchmark_analysis = analyze_benchmarks(
            benchmark_data, report_dates, as_of_date, previous_as_of_date,
            report_config["report"]["recent_windows"])
        style_sources = dict(benchmark_data)
        style_sources.update(style_data)
        style_analysis = analyze_style_proxies(
            style_sources, report_config["style"]["proxies"], report_dates, as_of_date,
            previous_as_of_date, report_config["report"]["recent_windows"],
            report_config["style"]["heatmap_weeks"],
            report_config["style"]["max_staleness_days"],
            report_config["style"]["neutral_spread_threshold"])
        universe = analyze_universe(
            observations, report_dates, as_of_date, previous_as_of_date,
            report_config["strategies"], report_config["report"]["min_sample_size"],
            report_config["report"]["recent_windows"])
        alpha_config = report_config["alpha_heatmap"]
        alpha_heatmap = analyze_alpha_heatmap(
            observations, report_dates, report_config["strategies"],
            report_config["report"]["min_sample_size"], alpha_config["weeks"],
            alpha_config["neutral_excess_threshold"])
        alpha_heatmap["enabled"] = alpha_config["enabled"]
        size_analysis = analyze_size_groups(
            observations, as_of_date, report_config["strategies"],
            report_config["size_groups"])
        benchmark_returns = {
            strategy_key: next(
                (item["weekly_return"] for item in benchmark_analysis["benchmarks"]
                 if item["benchmark_key"] == details["benchmark_key"]), None)
            for strategy_key, details in report_config["strategies"].items()
        }
        focus_cards, focus_warnings = build_focus_manager_cards(
            focus_config, universe, observations, report_dates, as_of_date,
            report_config["strategies"], benchmark_returns)
        alerts = detect_anomalies(universe, observations, as_of_date, report_config, focus_config)
        facts = build_facts(
            args.db, args.benchmark, style_path, as_of_date, previous_as_of_date, report_config,
            benchmark_analysis, style_analysis, universe, alpha_heatmap, size_analysis,
            focus_cards, focus_warnings, alerts)
        if args.validate_only:
            _print_summary(facts, validate_only=True)
            return 0

        output_dir = args.output_dir or _project_path(report_config["report"].get("output_dir", "reports/weekly"))
        facts_dir = args.facts_dir or _project_path(report_config["report"].get("facts_dir", "data/derived/weekly"))
        report_path = output_dir / (as_of_date + ".md")
        dated_facts_dir = facts_dir / as_of_date
        facts_path = dated_facts_dir / "report_facts.json"
        validation_path = dated_facts_dir / "report_validation.json"
        existing = [path for path in (report_path, facts_path, validation_path) if path.exists()]
        if existing and not args.overwrite:
            raise AnalyticsError("Report artifacts already exist; use --overwrite to replace: {}".format(", ".join(str(path) for path in existing)))
        report = render_report(
            facts, report_config["display"]["percent_digits"],
            report_config["display"]["max_focus_managers"],
            report_config["display"]["max_alerts"])
        write_json_atomic(facts_path, facts)
        write_json_atomic(validation_path, {
            "status": "ok",
            "as_of_date": as_of_date,
            "facts_path": str(facts_path),
            "warning_count": len(facts["data_quality"]["warnings"]),
        })
        write_text_atomic(report_path, report)
        _print_summary(facts, validate_only=False, report_path=report_path, facts_path=facts_path)
        return 0
    except AnalyticsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _print_summary(facts, validate_only, report_path=None, facts_path=None):
    prefix = "Validated" if validate_only else "Generated"
    print("{} weekly report facts for {}".format(prefix, facts["as_of_date"]))
    print("Strategies: {} | warnings: {}".format(
        len(facts["strategy_summary"]), len(facts["data_quality"]["warnings"])))
    if report_path:
        print(f"Report: {report_path}")
    if facts_path:
        print(f"Facts: {facts_path}")


if __name__ == "__main__":
    raise SystemExit(main())
