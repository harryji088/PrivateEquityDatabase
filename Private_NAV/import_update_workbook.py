"""Import the wide-format inbox/更新.xlsx file into the private NAV library."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
from openpyxl import load_workbook

from update_nav_library import LIBRARY, ROOT, classify, existing_dates, product_codes, update_library, write_report


# Source product name: (date column, unit NAV column, optional cumulative NAV column, canonical product name)
COLUMN_MAP = {
    "景林精选1号": (0, 1, None, "景林精选1号"),
    "景林精选FOF证券投资子HM1期": (3, 4, None, "景林精选FOF证券投资子HM1期"),
    "高毅晓峰精选8号": (6, 7, None, "华润信托-高毅晓峰精选8号"),
    "孝庸魔方汇股票优选二号": (13, 14, None, "孝庸魔方汇股票优选二号"),
    "平方和1000": (16, 17, None, "平方和鼎盛中证1000指数增强127号A期"),
    "顽岩量选": (19, 20, None, "顽岩君盈全市场选股6号1期"),
    "杉树他山": (23, 24, None, "杉树他山"),
    "诚奇睿盈500指增": (26, 27, None, "诚奇睿盈500指增"),
    "宽德飞虹三期": (29, 30, 31, "宽德飞虹三期"),
    "半夏宏观对冲": (33, 34, None, "半夏宏观对冲"),
    "源乐晟新晟2期": (36, 37, None, "源乐晟新晟优选2期"),
    "孝庸魔方汇一号B": (40, 41, None, "孝庸魔方汇股票优选一号B"),
}


def as_number(value) -> Optional[float]:
    number = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(number) else float(number)


def parse_source(path: Path) -> Tuple[List[dict], List[str]]:
    frame = pd.read_excel(path, header=None)
    records: List[dict] = []
    for source_name, (date_column, unit_column, cumulative_column, canonical_name) in COLUMN_MAP.items():
        for _, row in frame.iloc[2:].iterrows():
            value_date = pd.to_datetime(row.iloc[date_column], errors="coerce")
            unit_nav = as_number(row.iloc[unit_column])
            if pd.isna(value_date) or unit_nav is None or value_date.date() > date.today():
                continue
            cumulative_nav = unit_nav if cumulative_column is None else as_number(row.iloc[cumulative_column])
            if cumulative_nav is None:
                cumulative_nav = unit_nav
            records.append({
                "source_file": path.name,
                "observed_name": source_name,
                "matched_name": canonical_name,
                "date": value_date.date(),
                "unit_nav": unit_nav,
                "cumulative_nav": cumulative_nav,
                "status": "accepted",
                "notes": "更新.xlsx 导入",
            })
    skipped = ["衍复全指指增"]
    return records, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="导入 inbox/更新.xlsx 的完整历史净值")
    parser.add_argument("--source", type=Path, default=ROOT.parent / "inbox" / "更新.xlsx")
    parser.add_argument("--apply", action="store_true", help="实际更新私募净值.xlsx；默认只校验和生成汇总")
    args = parser.parse_args()
    try:
        records, skipped = parse_source(args.source)
        codes = product_codes()
        existing = existing_dates(load_workbook(LIBRARY, data_only=True))
        additions, review = classify(records, codes, existing)
        report = write_report(additions, review)
        if args.apply and additions:
            backup = update_library(additions)
            print("净值库已更新，备份: {}".format(backup))
        print("更新.xlsx 解析 {} 条有效净值，新增 {} 条，冲突/重复 {} 条。".format(
            len(records), len(additions), len(review)
        ))
        print("未导入（不在产品名单）: {}".format("、".join(skipped)))
        print("本次汇总: {}".format(report))
        return 0
    except Exception as exc:
        print("处理失败: {}".format(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
