import argparse
import json

from scripts import update_style_indices


def _config(path, output_path):
    path.write_text(
        "style:\n"
        f"  data_path: {output_path}\n"
        "  max_staleness_days: 4\n"
        "  indices:\n"
        "    A:\n"
        "      label: 指数A\n"
        "      source_key: 指数A\n"
        "      wind_code: A.CSI\n"
        "      csindex_code: A\n"
        "    B:\n"
        "      label: 指数B\n"
        "      source_key: 指数B\n"
        "      wind_code: B.CSI\n"
        "      csindex_code: B\n",
        encoding="utf-8",
    )


def _series(label, code):
    return {
        "label": label, "wind_code": f"{code}.CSI", "csindex_code": code,
        "dates": ["20260101"], "navs": [1.0],
    }


def test_default_update_failure_leaves_existing_cache_unchanged(tmp_path, monkeypatch):
    output = tmp_path / "style.json"
    original = {"指数A": _series("指数A", "A"), "指数B": _series("指数B", "B")}
    output.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
    before = output.read_bytes()
    config = tmp_path / "report.yaml"
    _config(config, output)
    monkeypatch.setattr(update_style_indices, "parse_args", lambda: argparse.Namespace(
        config=config, output=None, start_date="20260101", end_date="20260102",
        allow_partial=False,
    ))

    def fake_fetch(code, _start, _end):
        if code == "B":
            raise RuntimeError("simulated failure")
        return {"20260101": 100.0, "20260102": 101.0}

    monkeypatch.setattr(update_style_indices, "fetch_index_data", fake_fetch)

    assert update_style_indices.main() == 2
    assert output.read_bytes() == before


def test_allow_partial_requires_complete_fresh_validated_fallbacks(tmp_path, monkeypatch):
    output = tmp_path / "style.json"
    original = {"指数A": _series("指数A", "A"), "指数B": _series("指数B", "B")}
    output.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
    config = tmp_path / "report.yaml"
    _config(config, output)
    monkeypatch.setattr(update_style_indices, "parse_args", lambda: argparse.Namespace(
        config=config, output=None, start_date="20260101", end_date="20260102",
        allow_partial=True,
    ))

    def fake_fetch(code, _start, _end):
        if code == "B":
            raise RuntimeError("simulated failure")
        return {"20260101": 100.0, "20260102": 101.0}

    monkeypatch.setattr(update_style_indices, "fetch_index_data", fake_fetch)

    assert update_style_indices.main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["指数A"]["dates"][-1] == "20260102"
    assert payload["指数B"]["dates"][-1] == "20260101"


def test_extend_is_bridge_scaled_and_idempotent():
    existing = {"dates": ["20260101", "20260102"], "navs": [1.0, 1.1]}
    fresh = {"20260102": 220.0, "20260103": 242.0}

    extended = update_style_indices._extend(existing, fresh)
    repeated = update_style_indices._extend(extended, {"20260103": 242.0})

    assert extended == {
        "dates": ["20260101", "20260102", "20260103"],
        "navs": [1.0, 1.1, 1.21],
    }
    assert repeated == extended
