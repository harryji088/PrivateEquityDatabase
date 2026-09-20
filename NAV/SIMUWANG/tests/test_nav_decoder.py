from __future__ import annotations

import base64
import importlib.util
import io
import unittest
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw


MODULE_PATH = Path(__file__).resolve().parents[1] / "nav_decoder.py"
SPEC = importlib.util.spec_from_file_location("simuwang_nav_decoder", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
nav_decoder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nav_decoder)


def character_data_url(character: str) -> str:
    image = Image.new("RGBA", (24, 44), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if character == ".":
        draw.rectangle((9, 35, 13, 39), fill=(35, 35, 35, 255))
    else:
        segments = {
            "0": "ab cdef".replace(" ", ""),
            "1": "bc",
            "2": "abdeg",
            "3": "abcdg",
            "4": "bcfg",
            "5": "acdfg",
            "6": "acdefg",
            "7": "abc",
            "8": "abcdefg",
            "9": "abcdfg",
        }[character]
        coordinates = {
            "a": (4, 3, 19, 6),
            "b": (17, 5, 20, 20),
            "c": (17, 21, 20, 36),
            "d": (4, 35, 19, 38),
            "e": (3, 21, 6, 36),
            "f": (3, 5, 6, 20),
            "g": (4, 19, 19, 22),
        }
        for segment in segments:
            draw.rectangle(coordinates[segment], fill=(35, 35, 35, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def encoded_value(value: str):
    return [character_data_url(character) for character in value]


class CalibrationTests(unittest.TestCase):
    def test_reconstructs_known_sample(self) -> None:
        changes = ["-1.32%", "1.95%", "10.84%", "-0.13%"]
        values = nav_decoder.reconstruct_reinvested_navs(
            changes, Decimal("1.8435")
        )
        self.assertEqual(
            [nav_decoder.format_nav(value) for value in values],
            ["1.8435", "1.8682", "1.8325", "1.6533"],
        )

    def test_latest_nav_from_return(self) -> None:
        self.assertEqual(
            nav_decoder.latest_nav_from_return("84.35%"), Decimal("1.8435")
        )


class GlyphDecodeTests(unittest.TestCase):
    def test_decodes_and_validates_rows(self) -> None:
        raw_rows = [
            {
                "date": "2026-01-09",
                "change_pct": "10.00%",
                "nav_cells": [
                    encoded_value("1.1000"),
                    encoded_value("1.1000"),
                    encoded_value("1.1000"),
                ],
            },
            {
                "date": "2025-12-31",
                "change_pct": "0.00%",
                "nav_cells": [
                    encoded_value("1.0000"),
                    encoded_value("1.0000"),
                    encoded_value("1.0000"),
                ],
            },
        ]
        decoded = nav_decoder.decode_nav_rows(raw_rows, Decimal("1.1000"))
        self.assertEqual(decoded[0]["unit_nav"], "1.1000")
        self.assertEqual(decoded[1]["cumulative_nav_reinvest"], "1.0000")


if __name__ == "__main__":
    unittest.main()
