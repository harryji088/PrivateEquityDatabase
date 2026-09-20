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
SPEC = importlib.util.spec_from_file_location("simuwang_scrape_nav", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
scrape_nav = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scrape_nav)


class ProductListTests(unittest.TestCase):
    def test_chinese_headers_and_optional_latest_nav(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "products.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["产品名称", "产品地址", "最新累计净值"])
                writer.writerow(
                    [
                        "顽岩量化选股1号",
                        "https://dc.simuwang.com/product/HF0000CB02.html?chat_off=0",
                        "1.8435",
                    ]
                )
            products = scrape_nav.load_products(path)

        self.assertEqual(products[0]["fund_id"], "HF0000CB02")
        self.assertEqual(products[0]["latest_cumulative_nav"], "1.8435")


class ReturnPatternTests(unittest.TestCase):
    def test_inception_return_pattern(self) -> None:
        text = "成立来收益(1.5年) ：\n84.35%\n累计净值："
        match = scrape_nav.RETURN_RE.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "84.35")


class ProductMetadataTests(unittest.TestCase):
    def test_extract_product_registration_code(self) -> None:
        text = "基金经理：吕杰勇\n备案编号：\nSXN345\n公司管理规模：100亿以上"
        self.assertEqual(scrape_nav.extract_registration_code(text), "SXN345")

    def test_output_filename_uses_registration_code(self) -> None:
        path = scrape_nav.product_output_path(
            Path("output"),
            "SXN345",
            "平方和/鼎盛中证1000指数增强8号",
            [{"date": "2022-10-14"}, {"date": "2026-08-21"}],
        )
        self.assertEqual(
            path.name,
            "SXN345-平方和_鼎盛中证1000指数增强8号-20221014-20260821.csv",
        )


if __name__ == "__main__":
    unittest.main()
