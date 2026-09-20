"""
核心计算逻辑单元测试。

覆盖 backend/scripts/import_weekly_sqlite.py 中的关键计算：
  - compute_excess_drawdown : 超额回撤的 peak 跟踪与相对回撤
  - compute_stock_long_excess: 基准周收益 + 超额收益复利累积

这些计算"算错不报错、只给出错误数字"，是数据正确性的最大风险点，
因此优先用单元测试锁定其行为。
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

# 让测试可以 import backend/scripts 下的脚本
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import import_weekly_sqlite as iws  # noqa: E402

# 周度 (record_date, week_label) 基底，供 _insert_weeks 复用
_WEEK_BASE = [
    ("2026-01-09", "2026-W01"), ("2026-01-16", "2026-W02"),
    ("2026-01-23", "2026-W03"), ("2026-01-30", "2026-W04"),
    ("2026-02-06", "2026-W05"), ("2026-02-13", "2026-W06"),
]


def _make_conn():
    """建一个内存 SQLite 并套用真实 schema。"""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    iws.create_schema(conn)
    return conn


def _insert_fund(conn, company="测试公司", strategy="index_500"):
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO fund_companies(name) VALUES(?)", (company,))
    cid = cur.execute(
        "SELECT id FROM fund_companies WHERE name=?", (company,)).fetchone()[0]
    cur.execute(
        "INSERT OR IGNORE INTO funds(company_id, name, strategy_type) VALUES(?,?,?)",
        (cid, f"{company}-{strategy}", strategy))
    fid = cur.execute(
        "SELECT id FROM funds WHERE company_id=? AND strategy_type=?",
        (cid, strategy)).fetchone()[0]
    return fid


def _insert_ytd_excess(conn, fid, seq):
    """按 _WEEK_BASE 顺序插入一组 ytd_excess。"""
    cur = conn.cursor()
    for (rd, wl), ytd_ex in zip(_WEEK_BASE, seq):
        cur.execute(
            "INSERT INTO weekly_performances(fund_id, week_label, record_date, ytd_excess) "
            "VALUES(?,?,?,?)", (fid, wl, rd, ytd_ex))
    conn.commit()


# ───────────────────────── compute_excess_drawdown ─────────────────────────

def test_excess_drawdown_tracks_peak():
    """excess_nav 上升→峰→回撤→仍低于峰→新高，回撤应正确跟踪历史峰值。"""
    conn = _make_conn()
    fid = _insert_fund(conn)
    # excess_nav = 1 + ytd_excess: 1.00 → 1.05(峰) → 1.02 → 1.04 → 1.06(新高)
    _insert_ytd_excess(conn, fid, [0.00, 0.05, 0.02, 0.04, 0.06])
    cur = conn.cursor()
    iws.compute_excess_drawdown(conn, cur)

    dds = [r[0] for r in cur.execute(
        "SELECT ytd_excess_drawdown FROM weekly_performances WHERE fund_id=? "
        "ORDER BY record_date", (fid,)).fetchall()]
    expected = [
        0.0,                          # 1.00, peak=1.00
        0.0,                          # 1.05, peak=1.05
        (1.02 - 1.05) / 1.05,         # 回撤
        (1.04 - 1.05) / 1.05,         # 仍低于峰
        0.0,                          # 1.06 新高
    ]
    assert len(dds) == len(expected)
    for got, exp in zip(dds, expected):
        assert got == pytest.approx(exp, abs=1e-6)


def test_excess_drawdown_monotone_decline_all_negative():
    """单调下行序列：首期为 0，其后每期相对首期峰值均为负回撤。"""
    conn = _make_conn()
    fid = _insert_fund(conn)
    _insert_ytd_excess(conn, fid, [0.00, -0.01, -0.03, -0.02])
    cur = conn.cursor()
    iws.compute_excess_drawdown(conn, cur)
    dds = [r[0] for r in cur.execute(
        "SELECT ytd_excess_drawdown FROM weekly_performances WHERE fund_id=? "
        "ORDER BY record_date", (fid,)).fetchall()]
    assert dds[0] == 0.0
    for d in dds[1:]:
        assert d < 0.0


def test_excess_drawdown_never_positive():
    """回撤定义上 <= 0，任何情况下不应出现正值。"""
    conn = _make_conn()
    fid = _insert_fund(conn)
    _insert_ytd_excess(conn, fid, [0.03, 0.05, 0.01, 0.08, 0.02])
    cur = conn.cursor()
    iws.compute_excess_drawdown(conn, cur)
    dds = [r[0] for r in cur.execute(
        "SELECT ytd_excess_drawdown FROM weekly_performances WHERE fund_id=? "
        "ORDER BY record_date", (fid,)).fetchall()]
    assert all(d <= 1e-12 for d in dds)


# ─────────────────────── compute_stock_long_excess ─────────────────────────

def test_stock_long_excess_compounding(tmp_path, monkeypatch):
    """几何超额：weekly_excess=(1+fr)/(1+br)-1；ytd_excess=(1+fund_ytd)/(1+bench_cum)-1。"""
    conn = _make_conn()
    fid = _insert_fund(conn, company="选股公司", strategy="stock_long")
    cur = conn.cursor()

    # 基金近一周收益率：3 周
    fund_weekly = [0.02, 0.01, -0.005]
    weeks = _WEEK_BASE[:3]
    # 累计 ytd_return = Π(1+weekly) - 1（与 1231 年初基线一致）
    fund_ytd = []
    _acc = 1.0
    for r in fund_weekly:
        _acc *= (1 + r)
        fund_ytd.append(_acc - 1)
    for (rd, wl), r, ytd in zip(weeks, fund_weekly, fund_ytd):
        cur.execute(
            "INSERT INTO weekly_performances(fund_id, week_label, record_date, weekly_return, ytd_return) "
            "VALUES(?,?,?,?,?)", (fid, wl, rd, r, ytd))
    conn.commit()

    # 临时中证1000 基准：含 20251231 年初基线（几何累计超额 ytd_excess 依赖它）
    # 周收盘 NAV 隐含基准周收益: +1.0%, +0.5%, -1.0%
    bench = {
        "中证1000": {
            "dates": ["20251231", "20260109", "20260116", "20260123"],
            "navs": [1.0, 1.01, 1.01 * 1.005, 1.01 * 1.005 * 0.99],
        }
    }
    (tmp_path / "benchmark_nav.json").write_text(
        json.dumps(bench), encoding="utf-8")

    # 函数优先读 PROJECT_ROOT/benchmark_nav.json(绝对路径，真实存在)；
    # 这里强制其 fallback 到 CWD 下的临时文件，以隔离测试。
    real_exists = os.path.exists
    monkeypatch.setattr(
        os.path, "exists",
        lambda p: False if (os.path.isabs(p) and p.endswith("benchmark_nav.json"))
        else real_exists(p))
    monkeypatch.chdir(tmp_path)

    iws.compute_stock_long_excess(conn, cur)

    rows = cur.execute(
        "SELECT weekly_excess, ytd_excess FROM weekly_performances "
        "WHERE fund_id=? ORDER BY record_date", (fid,)).fetchall()

    b = bench["中证1000"]["navs"]  # [1231, 0109, 0116, 0123]
    # 基准周收益：首周锚定 1231，其后逐周环比
    bench_weekly = [b[1] / b[0] - 1, b[2] / b[1] - 1, b[3] / b[2] - 1]
    # 基准自年初累计 = 各周 NAV / 1231 NAV - 1
    bench_cum = [b[1] / b[0] - 1, b[2] / b[0] - 1, b[3] / b[0] - 1]
    for (we, ytd_e), fr, ytd_r, br, bc in zip(
            rows, fund_weekly, fund_ytd, bench_weekly, bench_cum):
        # 单周几何超额
        assert we == pytest.approx((1 + fr) / (1 + br) - 1, abs=1e-6)
        # 累计几何超额 = (1+基金累计) / (1+基准累计) - 1
        assert ytd_e == pytest.approx((1 + ytd_r) / (1 + bc) - 1, abs=1e-6)


def test_stock_long_excess_missing_fund_week_skipped(tmp_path, monkeypatch):
    """某周基金无数据时该周被跳过；各周累计超额基于自身 ytd_return 独立计算，不依赖相邻周。"""
    conn = _make_conn()
    fid = _insert_fund(conn, company="选股公司2", strategy="stock_long")
    cur = conn.cursor()
    # 只插第 1、3 周，跳过第 2 周；各自带 ytd_return（几何累计超额的输入）
    cur.execute(
        "INSERT INTO weekly_performances(fund_id, week_label, record_date, weekly_return, ytd_return) "
        "VALUES(?,?,?,?,?)", (fid, "2026-W01", "2026-01-09", 0.02, 0.02))
    cur.execute(
        "INSERT INTO weekly_performances(fund_id, week_label, record_date, weekly_return, ytd_return) "
        "VALUES(?,?,?,?,?)", (fid, "2026-W03", "2026-01-23", 0.03, 0.05))
    conn.commit()

    (tmp_path / "benchmark_nav.json").write_text(json.dumps({
        "中证1000": {"dates": ["20251231", "20260109", "20260116", "20260123"],
                     "navs": [1.0, 1.01, 1.015, 1.02]}
    }), encoding="utf-8")
    real_exists = os.path.exists
    monkeypatch.setattr(
        os.path, "exists",
        lambda p: False if (os.path.isabs(p) and p.endswith("benchmark_nav.json"))
        else real_exists(p))
    monkeypatch.chdir(tmp_path)

    iws.compute_stock_long_excess(conn, cur)

    rows = cur.execute(
        "SELECT week_label, weekly_excess, ytd_excess FROM weekly_performances "
        "WHERE fund_id=? ORDER BY record_date", (fid,)).fetchall()
    # 只有数据的两周被填充，缺失周不报错
    assert len(rows) == 2
    assert rows[0][0] == "2026-W01"
    assert rows[1][0] == "2026-W03"
    # 各周累计超额非空，且基于自身 ytd_return 与基准累计独立算出（中间缺失周不影响）
    b = [1.0, 1.01, 1.015, 1.02]  # 1231, 0109, 0116, 0123
    # 基准周收益：DB 在场周=[W01,W03]，W03 环比上一在场周 W01
    bench_weekly = {"2026-W01": b[1] / b[0] - 1, "2026-W03": b[3] / b[1] - 1}
    bench_cum = {"2026-W01": b[1] / b[0] - 1, "2026-W03": b[3] / b[0] - 1}
    fund = {"2026-W01": (0.02, 0.02), "2026-W03": (0.03, 0.05)}
    for wl, we, ytd_e in rows:
        fr, ytd_r = fund[wl]
        assert we == pytest.approx((1 + fr) / (1 + bench_weekly[wl]) - 1, abs=1e-6)
        assert ytd_e == pytest.approx((1 + ytd_r) / (1 + bench_cum[wl]) - 1, abs=1e-6)
