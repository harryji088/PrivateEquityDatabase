from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))
MODULE_PATH = MODULE_DIR / "scrape_nav.py"
SPEC = importlib.util.spec_from_file_location("howbuy_scrape_nav", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
scrape_nav = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scrape_nav)


class UrlTests(unittest.TestCase):
    def test_detail_url_becomes_history_url(self) -> None:
        product, history, fund_id = scrape_nav.normalize_history_url(
            "https://simu.howbuy.com/shanghaikuandesimu/SZP078/"
        )
        self.assertEqual(
            product,
            "https://simu.howbuy.com/shanghaikuandesimu/SZP078/",
        )
        self.assertEqual(
            history,
            "https://simu.howbuy.com/shanghaikuandesimu/SZP078/lsjz",
        )
        self.assertEqual(fund_id, "SZP078")

    def test_history_url_is_idempotent(self) -> None:
        _, history, fund_id = scrape_nav.normalize_history_url(
            "https://simu.howbuy.com/shanghaikuandesimu/SZP078/lsjz?x=1"
        )
        self.assertEqual(
            history,
            "https://simu.howbuy.com/shanghaikuandesimu/SZP078/lsjz",
        )
        self.assertEqual(fund_id, "SZP078")


class ProductListTests(unittest.TestCase):
    def test_chinese_headers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "products.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["产品名称", "产品地址"])
                writer.writerow(
                    [
                        "宽德中证1000指增8号臻享一期",
                        "https://simu.howbuy.com/shanghaikuandesimu/SZP078/lsjz",
                    ]
                )
            products = scrape_nav.load_products(path)

        self.assertEqual(products[0]["fund_id"], "SZP078")
        self.assertTrue(products[0]["history_url"].endswith("/lsjz"))


class TableParserTests(unittest.TestCase):
    def test_parse_normal_table(self) -> None:
        snapshot = {
            "headers": ["净值日期", "单位净值", "累计净值", "涨跌幅"],
            "rows": [
                ["2026-08-21", "1.2345", "1.5678", "+1.20%"],
                ["2026/08/14", "1.2200*", "1.5492", "-0.30%"],
            ],
        }
        rows = scrape_nav.parse_history_snapshot(snapshot)
        self.assertEqual(rows[0]["date"], "2026-08-21")
        self.assertEqual(rows[1]["date"], "2026-08-14")
        self.assertEqual(rows[1]["unit_nav"], "1.2200")

    def test_reject_login_placeholder(self) -> None:
        snapshot = {
            "headers": ["净值日期", "单位净值", "累计净值"],
            "rows": [["2026-08-21", "登录可见", "登录可见"]],
        }
        with self.assertRaises(scrape_nav.ScrapeError):
            scrape_nav.parse_history_snapshot(snapshot)


class OutputFilenameTests(unittest.TestCase):
    def test_product_code_name_and_date_range(self) -> None:
        rows = [
            {"date": "2026-08-21"},
            {"date": "2023-04-14"},
        ]
        path = scrape_nav.product_output_path(
            Path("output"),
            {"fund_id": "SZP078"},
            "宽德/中证1000指增8号臻享一期",
            rows,
        )
        self.assertEqual(
            path.name,
            "SZP078-宽德_中证1000指增8号臻享一期-20230414-20260821.csv",
        )


if __name__ == "__main__":
    unittest.main()
