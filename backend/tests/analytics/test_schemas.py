from pathlib import Path

import pytest
import yaml

from analytics.schemas import AnalyticsError, load_report_config

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _config():
    return yaml.safe_load(
        (PROJECT_ROOT / "config/weekly_report.yaml").read_text(encoding="utf-8"))


def test_v1_requires_report_windows_used_by_renderer(tmp_path):
    config = _config()
    config["report"]["recent_windows"] = [1, 4]
    path = tmp_path / "report.yaml"
    path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    with pytest.raises(AnalyticsError, match="must include 4 and 12"):
        load_report_config(path)


def test_v1_rejects_timezone_not_supported_by_generated_at(tmp_path):
    config = _config()
    config["report"]["timezone"] = "UTC"
    path = tmp_path / "report.yaml"
    path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    with pytest.raises(AnalyticsError, match="must be Asia/Shanghai"):
        load_report_config(path)


def test_alpha_heatmap_config_validates_boolean_window_and_threshold(tmp_path):
    config = _config()
    config["alpha_heatmap"]["enabled"] = "yes"
    path = tmp_path / "report.yaml"
    path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    with pytest.raises(AnalyticsError, match="enabled must be boolean"):
        load_report_config(path)

    config = _config()
    config["alpha_heatmap"]["neutral_excess_threshold"] = 1
    path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    with pytest.raises(AnalyticsError, match="must be < 1"):
        load_report_config(path)


def test_size_group_config_rejects_overlap_and_invalid_threshold(tmp_path):
    config = _config()
    config["size_groups"]["groups"]["small"]["categories"].append("100亿以上")
    path = tmp_path / "report.yaml"
    path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    with pytest.raises(AnalyticsError, match="must not overlap"):
        load_report_config(path)

    config = _config()
    config["size_groups"]["size_effect_min_gap"] = 1
    path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    with pytest.raises(AnalyticsError, match="must be < 1"):
        load_report_config(path)
