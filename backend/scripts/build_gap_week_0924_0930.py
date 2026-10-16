#!/usr/bin/env python3
"""用 0930 月度业绩榜补 0924-0930 缺失周的量化股票合成周报.

背景: 点睛周度榜单在 0921-0924 与 0930-1009 之间缺了 0924-0930 一周
(9/25、9/28-9/30 共 4 个交易日),而 0930-1009 周报的"近一周"经基准反推
精确对应 0930→1009,月度榜(0831-0930)提供了净值日期 2026-09-30 的
"今年以来收益率"。因此缺失周可由两端 YTD 几何推导:

    近一周收益率  = (1 + YTD@0930) / (1 + YTD@0924) - 1
    近一周超额    = (1 + YTD超额@0930) / (1 + YTD超额@0924) - 1   (仅指增)

产出合成周 xlsx 放入正本目录(周度业绩/2026/量化股票/),标题与
"数据说明"sheet 明确标注合成属性;导入器按常规周解析。

口径校验(2026-10-16 实测): 三文件交集 302 只产品,
(1+YTD@1009)/(1+YTD@0930月度)-1 与 0930-1009 周报周收益中位误差 0.3-0.4bp;
指增由 YTD 超额差反推的基准收益与基准 0924→0930 实际值中位误差 ≤0.4bp。

覆盖率: 312/316。月度榜未收录的基金(九坤-500、玄信-2000、赜远-A500、
青岛永誉天泽-1000)与 0921-0924 未上榜的陆生生-中性 该周留空。
"成立以来"四列与 2025 年度收益率月度榜没有,留空不造数。
"""

import sys
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from import_weekly_sqlite import COMPANY_NAME_NORMALIZE  # noqa: E402

ROOT = SCRIPT_DIR.parent.parent
M4_DIR = ROOT / "点睛焱究所" / "4. 周度业绩排名更新及业绩点评"
WEEK_PREV = M4_DIR / "周度业绩" / "2026" / "量化股票" / "点睛业绩放送_量化股票策略业绩榜（0921-0924）.xlsx"
WEEK_NEXT = M4_DIR / "周度业绩" / "2026" / "量化股票" / "点睛业绩放送_量化股票策略业绩榜（0930-1009）.xlsx"
MONTHLY = M4_DIR / "业绩排名(月度)" / "点睛业绩放送_全策略月度业绩榜20260930.xlsx"
OUTPUT = M4_DIR / "周度业绩" / "2026" / "量化股票" / "点睛业绩放送_量化股票策略业绩榜（0924-0930）.xlsx"

WEEK_LABEL = "0924-0930"
RECORD_DATE = "2026-09-30"

# 周报 sheet -> (月度榜 sheet, 是否有超额列)
SHEET_MAP = {
    "量化选股": ("量选", False),
    "市场中性": ("中性", False),
    "500指增": ("500", True),
    "1000指增": ("1000", True),
    "300指增": ("300", True),
    "2000指增": ("2000", True),
    "A500指增": ("A500", True),
}

# 指增周超额由月度榜"今年以来超额收益率"与周报"今年以来超额"几何推导
MAX_CHAIN_ERR = 5e-4  # 与 0930-1009 周报链式校验的中位误差上限 (5bp)


def norm(name):
    return COMPANY_NAME_NORMALIZE.get(name, name)


def read_sheet(ws):
    """按导入器同一规则定位表头,返回 {规范化名称: 行字段字典}。"""
    rows = list(ws.iter_rows(values_only=True))
    hdr = hi = None
    for i, r in enumerate(rows):
        cells = [str(c).strip() if c is not None else "" for c in r]
        if "基金管理人" in cells and "今年以来收益率" in cells:
            hdr, hi = cells, i
            break
    if hdr is None:
        raise ValueError(f"sheet {ws.title}: 未找到表头行")

    def col(label):
        return hdr.index(label) if label in hdr else None

    def col_like(*fragments, exclude=()):
        """列名子串匹配(周报/月度榜列名不同: 今年以来超额[收益率]、动态[最大]回撤)。"""
        for i, h in enumerate(hdr):
            if all(f in h for f in fragments) and not any(x in h for x in exclude):
                return i
        return None

    jc, jy = col("基金管理人"), col("今年以来收益率")
    js, jd = col("管理规模"), col("净值日期")
    jwr = col("近一周收益率")
    jye = col_like("今年以来超额", exclude=("回撤",))
    jxdd = col_like("今年以来动态回撤", "今年以来最大回撤", exclude=("超额",))
    out = {}
    for r in rows[hi + 1:]:
        raw = str(r[jc]).strip() if r[jc] else ""
        if not raw or "点睛" in raw:
            continue
        name = norm(raw)

        def val(idx):
            if idx is None or idx >= len(r) or r[idx] is None:
                return None
            try:
                return float(r[idx])
            except (TypeError, ValueError):
                return None

        rec = {
            "ytd": val(jy),
            "size": str(r[js]).strip() if js is not None and r[js] else None,
            "nav_date": str(r[jd]).strip()[:10] if jd is not None and r[jd] else RECORD_DATE,
            "ytd_excess": val(jye),
            "ytd_drawdown": val(jxdd),
            "weekly_return": val(jwr),
        }
        prev = out.get(name)
        if prev and prev["ytd"] != rec["ytd"]:
            raise ValueError(f"同名管理人 {name} 在 {ws.title} 中出现两行且 YTD 不同")
        out[name] = rec
    return out


def build_records():
    wb_prev = openpyxl.load_workbook(WEEK_PREV, read_only=True, data_only=True)
    wb_next = openpyxl.load_workbook(WEEK_NEXT, read_only=True, data_only=True)
    wb_m = openpyxl.load_workbook(MONTHLY, read_only=True, data_only=True)

    plan, report = {}, []
    for sheet, (msheet, has_excess) in SHEET_MAP.items():
        prev = read_sheet(wb_prev[sheet])
        monthly = read_sheet(wb_m[msheet])
        rows, skipped = [], []
        for name, p in prev.items():
            m = monthly.get(name)
            if m is None or m["ytd"] is None or p["ytd"] is None:
                skipped.append(name)
                continue
            weekly = (1 + m["ytd"]) / (1 + p["ytd"]) - 1
            rec = {
                "name": name,
                "size": m["size"] or p["size"],
                "nav_date": m["nav_date"],
                "weekly_return": weekly,
                "ytd_return": m["ytd"],
                "ytd_drawdown": m["ytd_drawdown"],
                "weekly_excess": None,
                "ytd_excess": None,
            }
            if has_excess:
                if m["ytd_excess"] is not None and p["ytd_excess"] is not None:
                    rec["weekly_excess"] = (1 + m["ytd_excess"]) / (1 + p["ytd_excess"]) - 1
                    rec["ytd_excess"] = m["ytd_excess"]
                else:
                    skipped.append(name)
                    continue
            rows.append(rec)
        rows.sort(key=lambda x: (-x["weekly_return"], x["name"]))
        for i, rec in enumerate(rows, 1):
            rec["rank"] = i
        plan[sheet] = rows
        rets = [r["weekly_return"] for r in rows]
        report.append(
            f"  {sheet}: 合成 {len(rows)} 只 | 周收益区间 [{min(rets):+.4f}, {max(rets):+.4f}]"
            f" | 该周留空 {sorted(skipped) if skipped else '无'}")

    # 链式校验: (1+YTD@1009)/(1+YTD@0930合成)-1 应≈ 0930-1009 周报周收益
    errs = []
    for sheet, (msheet, _) in SHEET_MAP.items():
        nxt = read_sheet(wb_next[sheet])
        for rec in plan[sheet]:
            n = nxt.get(rec["name"])
            if n and n["weekly_return"] is not None:
                errs.append(abs((1 + n["ytd"]) / (1 + rec["ytd_return"]) - 1 - n["weekly_return"]))
    median_err = sorted(errs)[len(errs) // 2]
    print(f"链式校验样本 {len(errs)} 只,中位误差 {median_err * 1e4:.2f}bp")
    if median_err > MAX_CHAIN_ERR:
        raise ValueError(f"链式校验中位误差 {median_err:.6f} 超过上限 {MAX_CHAIN_ERR},终止")

    wb_prev.close()
    wb_next.close()
    wb_m.close()
    return plan, report, median_err


def write_workbook(plan, report, median_err):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    bold = Font(bold=True)

    for sheet, rows in plan.items():
        ws = wb.create_sheet(sheet)
        has_excess = SHEET_MAP[sheet][1]
        header = ["序号", "策略类型", "基金管理人", "管理规模", "净值日期", "近一周收益率"]
        keys = ["rank", None, "name", "size", "nav_date", "weekly_return"]
        if has_excess:
            header += ["近一周超额"]
            keys += ["weekly_excess"]
        header += ["今年以来收益率"]
        keys += ["ytd_return"]
        if has_excess:
            header += ["今年以来超额"]
            keys += ["ytd_excess"]
        header += ["今年以来动态回撤"]
        keys += ["ytd_drawdown"]

        ws.cell(row=2, column=2, value=f"点睛业绩放送_{sheet}周度业绩榜（合成周 {WEEK_LABEL}）").font = bold
        ws.cell(row=2, column=2).alignment = Alignment(horizontal="left")
        # 与官方周报版式一致: A 列留空,数据从 B 列开始(导入器按 row[1] 找表头)
        for j, h in enumerate(header, 2):
            c = ws.cell(row=3, column=j, value=h)
            c.font = bold
        for i, rec in enumerate(rows):
            r = 4 + i
            for j, key in enumerate(keys, 2):
                if key is None:
                    c = ws.cell(row=r, column=j, value=sheet)
                elif key == "nav_date":
                    c = ws.cell(row=r, column=j, value=RECORD_DATE)
                else:
                    c = ws.cell(row=r, column=j, value=rec[key])
                if rec.get(key) is not None and ("收益率" in str(header[j - 2]) or "超额" in str(header[j - 2]) or "回撤" in str(header[j - 2])):
                    c.number_format = "0.00%"
        for j, h in enumerate(header, 2):
            ws.column_dimensions[openpyxl.utils.get_column_letter(j)].width = max(10, len(h) * 2 + 2)

    note = wb.create_sheet("数据说明")
    lines = [
        f"本文件为【合成周】数据,非点睛官方周报。生成时间: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"目的: 补齐 {WEEK_LABEL} 周(9/25、9/28-9/30,共 4 个交易日)。该周点睛未发布周度榜单,",
        "且 0930-1009 周报的\"近一周\"经基准反推精确对应 0930→1009(中证1000 隐含基准 -1.96% 完全吻合),",
        "故该周缺口只能由此处的月度榜单与 0921-0924 周报拼接推出。",
        "",
        "推导口径:",
        "  近一周收益率 = (1 + 月度榜今年以来收益率@0930) / (1 + 0921-0924周报今年以来收益率) - 1",
        "  近一周超额   = (1 + 月度榜今年以来超额收益率) / (1 + 周报今年以来超额) - 1   (仅指增,几何口径)",
        "  今年以来收益率/超额/动态回撤、管理规模、净值日期 直接取自月度榜(净值日期均为 2026-09-30)",
        "  排名 = 按合成周收益率降序;量化选股周超额由看板基于中证1000自算,此处留空,与官方周报一致",
        "",
        "留空不造数: \"成立以来\"年化收益/波动/夏普/动态回撤与 2025 年度收益率月度榜未提供,全部留空;",
        "月度榜未收录的基金(九坤-500、玄信-2000、赜远-A500、青岛永誉天泽-1000)及 0921-0924 未上榜的",
        "陆生生-中性 该周无记录。",
        "",
        "质量校验(生成时实测):",
    ] + report + [
        f"  链式校验: (1+YTD@1009)/(1+YTD@0930)-1 与 0930-1009 周报周收益中位误差 {median_err * 1e4:.2f}bp,阈值 {MAX_CHAIN_ERR * 1e4:.0f}bp",
        "",
        "相关说明见项目 点睛.md 与 backend/scripts/build_gap_week_0924_0930.py。",
    ]
    for i, line in enumerate(lines, 1):
        note.cell(row=i, column=1, value=line)

    wb.save(OUTPUT)
    return OUTPUT


def main():
    plan, report, median_err = build_records()
    total = sum(len(rows) for rows in plan.values())
    print("\n".join(report))
    print(f"合计合成 {total} 条记录")
    out = write_workbook(plan, report, median_err)
    print(f"\n已生成: {out}")


if __name__ == "__main__":
    main()
