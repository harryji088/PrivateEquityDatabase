from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scrape_nav.py"
SPEC = importlib.util.spec_from_file_location("fof99_scrape_nav", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
scrape_nav = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scrape_nav)


class ParseNavCellsTests(unittest.TestCase):
    def test_svg_digit_whitespace_is_removed(self) -> None:
        row = scrape_nav.parse_nav_cells(
            [
                "2026-08-21",
                "2\n.\n2\n0\n5\n5",
                "2\n.\n9\n4\n1\n0",
                "3\n.\n0\n0\n3\n3",
                "-\n0\n.\n3\n3\n%",
            ]
        )
        self.assertEqual(
            row,
            {
                "date": "2026-08-21",
                "unit_nav": "2.2055",
                "cumulative_nav": "2.9410",
                "adjusted_nav": "3.0033",
                "change_pct": "-0.33%",
            },
        )

    def test_non_data_row_is_ignored(self) -> None:
        self.assertIsNone(
            scrape_nav.parse_nav_cells(
                ["日期", "单位净值", "累计净值", "复权净值", "涨跌幅"]
            )
        )


class ProductListTests(unittest.TestCase):
    def test_chinese_headers_and_duplicate_urls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "products.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["产品名称", "产品地址"])
                writer.writerow(
                    [
                        "产品一",
                        "https://mp.fof99.com/fund/view/7478c9fd2a535fa0",
                    ]
                )
                writer.writerow(
                    [
                        "产品一重复",
                        "https://mp.fof99.com/fund/view/7478c9fd2a535fa0",
                    ]
                )

            products = scrape_nav.load_products(path)

        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["product_name"], "产品一")
        self.assertEqual(products[0]["product_code"], "7478c9fd2a535fa0")


class OutputTests(unittest.TestCase):
    def test_output_round_trip(self) -> None:
        row = {
            "product_name": "产品一",
            "product_code": "abc",
            "product_url": "https://mp.fof99.com/fund/view/abc",
            "date": "2026-08-21",
            "unit_nav": "1.1000",
            "cumulative_nav": "1.2000",
            "adjusted_nav": "1.3000",
            "change_pct": "1.00%",
            "scraped_at": "2026-08-25T12:00:00+08:00",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "output.csv"
            scrape_nav.atomic_write_rows(path, [row])
            loaded = scrape_nav.load_existing_rows(path)

        self.assertEqual(loaded[(row["product_url"], row["date"])], row)

    def test_output_filename(self) -> None:
        path = scrape_nav.product_output_path(
            Path("output"),
            {"product_code": "abc123"},
            "产品/一",
            [{"date": "2023-01-02"}, {"date": "2026-08-26"}],
        )
        self.assertEqual(path.name, "abc123-产品_一-20230102-20260826.csv")


class ProductMetadataTests(unittest.TestCase):
    def test_extract_registration_code_with_icon_character(self) -> None:
        text = "备案编号 \ue925 :\u00a0 SATW62\n私募管理人：上海顽岩"
        self.assertEqual(scrape_nav.extract_registration_code(text), "SATW62")

    def test_missing_registration_code(self) -> None:
        self.assertEqual(scrape_nav.extract_registration_code("产品名称"), "")


if __name__ == "__main__":
    unittest.main()
