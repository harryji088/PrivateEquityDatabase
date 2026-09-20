import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


def _create_fixture_database(path):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE fund_companies (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE funds (id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, name TEXT, strategy_type TEXT NOT NULL);
        CREATE TABLE weekly_performances (
            id INTEGER PRIMARY KEY, fund_id INTEGER NOT NULL, week_label TEXT NOT NULL,
            record_date TEXT NOT NULL, weekly_return REAL, weekly_excess REAL,
            ytd_return REAL, ytd_excess REAL, ytd_excess_drawdown REAL,
            size_category TEXT
        );
    """)
    dates = ["2026-01-02", "2026-01-09", "2026-01-16", "2026-01-23", "2026-01-30"]
    for manager_id, name in enumerate(("甲", "乙", "丙", "丁", "戊"), start=1):
        conn.execute("INSERT INTO fund_companies VALUES(?, ?)", (manager_id, name))
        conn.execute("INSERT INTO funds VALUES(?, ?, ?, ?)", (manager_id, manager_id, name + "-500", "index_500"))
        for index, day in enumerate(dates):
            weekly_excess = (manager_id - 3) * 0.002 + (0.001 if index == len(dates) - 1 else 0)
            conn.execute(
                "INSERT INTO weekly_performances VALUES(?,?,?,?,?,?,?,?,?,?)",
                (manager_id * 100 + index, manager_id, f"W{index}", day,
                 weekly_excess + 0.01, weekly_excess, weekly_excess + 0.01,
                 weekly_excess * (index + 1), min(0.0, weekly_excess), "0-5亿"),
            )
    conn.execute("INSERT INTO funds VALUES(100, 1, '甲-A500', 'index_a500')")
    conn.execute(
        "INSERT INTO weekly_performances VALUES(9999,100,'W5','2026-02-06',0.01,0.01,0.01,0.01,0.0,'100亿以上')"
    )
    conn.commit()
    conn.close()


def _run(args):
    return subprocess.run(
        [sys.executable, "scripts/generate_weekly_report.py"] + args,
        cwd=BACKEND_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_validates_then_generates_atomic_artifacts_without_network(tmp_path):
    database = tmp_path / "weekly.sqlite3"
    _create_fixture_database(database)
    benchmark = tmp_path / "benchmark_nav.json"
    shutil.copy(PROJECT_ROOT / "backend/tests/fixtures/benchmark_nav_sample.json", benchmark)
    style = tmp_path / "style_index_nav.json"
    shutil.copy(PROJECT_ROOT / "backend/tests/fixtures/style_index_nav_sample.json", style)
    output_dir = tmp_path / "reports"
    facts_dir = tmp_path / "facts"
    focus_config = tmp_path / "focus.yaml"
    focus_config.write_text(
        "version: 1\nfocus_managers:\n"
        "  - name: 甲\n    aliases: []\n    strategies: []\n"
        "    priority: high\n    enabled: true\n",
        encoding="utf-8",
    )
    arguments = [
        "--as-of", "2026-01-30", "--db", str(database), "--benchmark", str(benchmark),
        "--style", str(style),
        "--focus-config", str(focus_config),
        "--report-config", str(PROJECT_ROOT / "config/weekly_report.yaml"),
        "--output-dir", str(output_dir), "--facts-dir", str(facts_dir),
    ]
    validated = _run(arguments + ["--validate-only"])
    assert validated.returncode == 0, validated.stderr
    assert not output_dir.exists()

    configured_report = tmp_path / "weekly_report.yaml"
    configured_report.write_text(
        (PROJECT_ROOT / "config/weekly_report.yaml").read_text(encoding="utf-8").replace(
            "data_path: style_index_nav.json", f"data_path: {style}"),
        encoding="utf-8",
    )
    configured_style_args = [
        "--as-of", "2026-01-30", "--db", str(database),
        "--benchmark", str(benchmark), "--focus-config", str(focus_config),
        "--report-config", str(configured_report), "--validate-only",
    ]
    configured_style = _run(configured_style_args)
    assert configured_style.returncode == 0, configured_style.stderr

    generated = _run(arguments)
    assert generated.returncode == 0, generated.stderr
    assert (output_dir / "2026-01-30.md").is_file()
    facts = facts_dir / "2026-01-30/report_facts.json"
    assert facts.is_file()
    fact_payload = json.loads(facts.read_text(encoding="utf-8"))
    assert fact_payload["methodology"]["entity_grain"] == "manager_strategy"
    assert fact_payload["schema_version"] == "1.2"
    assert fact_payload["methodology"]["alpha_heatmap_grain"] == "strategy_report_week_cross_section"
    assert fact_payload["alpha_heatmap"]["weeks"][-1] == "2026-01-30"
    assert fact_payload["alpha_heatmap"]["strategies"][1]["history"][-1]["status"] == "positive"
    assert fact_payload["size_analysis"]["as_of_date"] == "2026-01-30"
    assert fact_payload["size_analysis"]["strategies"][1]["groups"][2]["sample_size"] == 5
    assert fact_payload["market"]["style"]["summary"]["available_proxy_count"] == 10
    assert [item["strategy_key"] for item in fact_payload["focus_managers"]] == ["index_500"]
    assert "## 9. 数据质量与口径" in (output_dir / "2026-01-30.md").read_text(encoding="utf-8")
    assert "### V2A 风格环境" in (output_dir / "2026-01-30.md").read_text(encoding="utf-8")
    assert "### 近12周 Alpha 热力图" in (output_dir / "2026-01-30.md").read_text(encoding="utf-8")
    assert "### 近12周正超额管理人比例" in (output_dir / "2026-01-30.md").read_text(encoding="utf-8")
    assert "## 6. 管理规模分组" in (output_dir / "2026-01-30.md").read_text(encoding="utf-8")

    repeat = _run(arguments)
    assert repeat.returncode == 2
    assert "--overwrite" in repeat.stderr

    overwritten = _run(arguments + ["--overwrite"])
    assert overwritten.returncode == 0, overwritten.stderr
