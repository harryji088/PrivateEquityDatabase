"""Seed script to populate database with realistic demo data.

Usage:
    python scripts/seed_data.py
"""

import sys
import random
import uuid
from datetime import date, timedelta
from pathlib import Path

import numpy as np

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import Base
from app.domains.companies.models import FundCompany
from app.domains.managers.models import FundManager
from app.domains.funds.models import Fund
from app.domains.nav.models import NavData
from app.domains.benchmarks.models import Benchmark, BenchmarkData
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# --- Configuration ---
NUM_COMPANIES = 12
NUM_MANAGERS = 25
NUM_FUNDS = 55
NAV_START_DATE = date(2022, 1, 1)
NAV_END_DATE = date(2026, 5, 30)

# Strategy weights for fund distribution
STRATEGIES = [
    "stock_long", "stock_long", "stock_long", "stock_long",
    "market_neutral", "market_neutral", "market_neutral",
    "cta", "cta", "cta",
    "arbitrage", "arbitrage",
    "macro_hedge", "macro_hedge",
    "bond", "bond",
    "multi_strategy", "multi_strategy",
    "fof", "fof",
    "quant", "quant",
]

# Realistic company names
COMPANY_NAMES = [
    ("淡水泉投资", "淡水泉", "2007-06-01", "北京", "P1001234"),
    ("高毅资产", "高毅", "2013-05-01", "上海", "P1001235"),
    ("景林资产", "景林", "2004-06-01", "上海", "P1001236"),
    ("重阳投资", "重阳", "2001-12-01", "上海", "P1001237"),
    ("千合资本", "千合", "2015-03-01", "深圳", "P1001238"),
    ("幻方量化", "幻方", "2015-06-01", "杭州", "P1001239"),
    ("九坤投资", "九坤", "2012-04-01", "北京", "P1001240"),
    ("明恒投资", "明恒", "2014-08-01", "上海", "P1001241"),
    ("灵均投资", "灵均", "2014-05-01", "北京", "P1001242"),
    ("衍复投资", "衍复", "2019-03-01", "上海", "P1001243"),
    ("天演资本", "天演", "2016-07-01", "上海", "P1001244"),
    ("诚奇资产", "诚奇", "2013-09-01", "深圳", "P1001245"),
]

MANAGER_NAMES = [
    ("赵军", "投资总监", 20, "清华大学硕士"),
    ("邓晓峰", "首席投资官", 22, "上海交通大学本科"),
    ("邱国鹭", "董事长", 25, "复旦大学博士"),
    ("蒋锦志", "创始人", 28, "浙江大学"),
    ("王亚伟", "总经理", 27, "中欧国际工商学院EMBA"),
    ("裘国根", "董事长", 30, "中国人民大学"),
    ("梁文锋", "技术总监", 10, "浙江大学博士"),
    ("王琛", "基金经理", 12, "清华大学博士"),
    ("姚齐聪", "量化总监", 10, "MIT博士"),
    ("蔡明", "CEO", 15, "上海交通大学"),
    ("马志刚", "基金经理", 14, "北京大学"),
    ("方建", "量化研究员", 8, "复旦大学博士"),
    ("徐阳", "投资经理", 18, "中国人民大学"),
    ("田宇", "策略总监", 16, "清华五道口"),
    ("刘宏", "合伙人", 20, "上海财经大学"),
    ("陈峰", "基金经理", 11, "南京大学"),
    ("张弛", "研究总监", 13, "武汉大学"),
    ("黄伟", "多策略负责人", 17, "中科大"),
    ("吴越", "量化经理", 9, "斯坦福硕士"),
    ("林鹏", "投资总监", 14, "厦门大学"),
    ("孙浩", "CTA主管", 12, "华东师范大学"),
    ("周明", "基金经理", 10, "中央财经大学"),
    ("郑磊", "套利策略负责人", 15, "南开大学"),
    ("钱进", "FOF投资经理", 13, "同济大学"),
    ("冯岩", "宏观策略总监", 19, "西南财经大学"),
]

BENCHMARKS_DATA = [
    ("沪深300", "CSI300", "stock_index"),
    ("中证500", "CSI500", "stock_index"),
    ("中证1000", "CSI1000", "stock_index"),
    ("中债综合指数", "CBI", "bond_index"),
    ("南华商品指数", "NHCI", "composite"),
]


def create_companies(session: Session) -> list[FundCompany]:
    companies = []
    for name, short, founding, city, code in COMPANY_NAMES:
        company = FundCompany(
            name=name,
            short_name=short,
            registration_code=code,
            registration_date=date.fromisoformat(founding) + timedelta(days=random.randint(30, 365)),
            founding_date=date.fromisoformat(founding),
            province="北京市" if city == "北京" else "上海市" if city == "上海" else "广东省" if city == "深圳" else "浙江省",
            city=city,
            total_aum=round(random.uniform(10, 500), 2),
            status="active",
            description=f"{name}是国内知名的私募基金管理公司。",
        )
        session.add(company)
        companies.append(company)
    session.flush()
    print(f"  Created {len(companies)} fund companies")
    return companies


def create_managers(session: Session, companies: list[FundCompany]) -> list[FundManager]:
    managers = []
    for i, (name, title, exp, edu) in enumerate(MANAGER_NAMES):
        company = companies[i % len(companies)]
        manager = FundManager(
            company_id=company.id,
            name=name,
            title=title,
            experience_years=float(exp) + random.uniform(-1, 1),
            education=edu,
            certifications="基金从业资格" + (", CFA" if random.random() > 0.7 else ""),
            bio=f"{name}拥有{exp}年投资经验，{edu}学历。",
        )
        session.add(manager)
        managers.append(manager)
    session.flush()
    print(f"  Created {len(managers)} fund managers")
    return managers


def create_benchmarks(session: Session) -> dict[str, Benchmark]:
    benchmarks = {}
    for name, code, category in BENCHMARKS_DATA:
        bm = Benchmark(name=name, code=code, category=category, description=f"{name}指数")
        session.add(bm)
        benchmarks[code] = bm
    session.flush()
    print(f"  Created {len(benchmarks)} benchmarks")
    return benchmarks


def generate_nav_series(
    start_date: date,
    end_date: date,
    initial_nav: float = 1.0,
    annual_return: float = 0.10,
    annual_vol: float = 0.15,
) -> list[dict]:
    """Generate a realistic NAV time series using geometric Brownian motion."""
    days = (end_date - start_date).days
    trading_days = int(days * 252 / 365)  # approximate
    dt = 1 / 252
    daily_vol = annual_vol * np.sqrt(dt)

    # Generate daily returns
    mu = annual_return * dt
    returns = np.random.normal(mu, daily_vol, trading_days)
    # Add slight autocorrelation for realism
    for i in range(1, len(returns)):
        returns[i] = 0.1 * returns[i - 1] + 0.9 * returns[i]

    # Build NAV series
    nav_values = []
    current_nav = initial_nav
    current_cum = initial_nav
    current_date = start_date

    for ret in returns:
        current_nav *= (1 + ret)
        current_cum *= (1 + ret)
        current_date += timedelta(days=1)
        # Skip weekends
        while current_date.weekday() >= 5:
            current_date += timedelta(days=1)
        if current_date > end_date:
            break

        nav_values.append({
            "date": current_date,
            "nav": round(current_nav, 6),
            "cumulative_nav": round(current_cum, 6),
            "daily_return": round(ret, 8),
        })

    return nav_values


def create_funds(
    session: Session,
    companies: list[FundCompany],
    managers: list[FundManager],
    benchmarks: dict[str, Benchmark],
) -> list[Fund]:
    """Generate diverse funds across strategies."""
    fund_names = {
        "stock_long": [
            ("价值精选1期", "淡水泉成长1期"),
            ("成长动力", "高毅精选价值"),
            ("景林价值成长", "重阳价值1期"),
            ("千合成长混合", "九坤股票优选"),
            ("明恒成长精选", "天演股票多头1号"),
        ],
        "market_neutral": [
            ("幻方市场中性1号", "九坤中性策略"),
            ("灵均量化中性", "衍复市场中性1号"),
            ("诚奇中性策略", "明恒量化对冲"),
            ("天演中性策略1号",),
        ],
        "cta": [
            ("千合CTA1号", "明恒商品趋势"),
            ("幻方CTA策略", "灵均管理期货1号"),
            ("九坤CTA复合策略", "衍复趋势跟踪"),
        ],
        "arbitrage": [
            ("天演套利策略1号", "衍复统计套利"),
            ("幻方套利策略", "灵均期权套利1号"),
            ("诚奇套利增强",),
        ],
        "macro_hedge": [
            ("高毅宏观对冲", "重阳全天候1号"),
            ("景林全球宏观", "千合宏观策略"),
            ("明恒宏观对冲1号",),
        ],
        "bond": [
            ("九坤债券增强", "明恒固收+"),
            ("高毅信用精选", "重阳债券1号"),
            ("景林固收策略",),
        ],
        "multi_strategy": [
            ("淡水泉多策略", "高毅全天候多策略"),
            ("千合多策略混合", "九坤多策略复合"),
            ("灵均多策略1号",),
        ],
        "fof": [
            ("景林FOF精选", "淡水泉母基金1号"),
            ("高毅组合基金", "明恒FOF稳健"),
            ("千合组合投资1号",),
        ],
        "quant": [
            ("幻方量化指增", "九坤量化精选"),
            ("灵均量化多因子", "衍复指数增强1号"),
            ("天演量化选股", "诚奇量化增强"),
        ],
    }

    bm_map = {
        "stock_long": "CSI300",
        "market_neutral": "CSI500",
        "cta": "NHCI",
        "arbitrage": "CSI500",
        "macro_hedge": "CSI300",
        "bond": "CBI",
        "multi_strategy": "CSI300",
        "fof": "CSI300",
        "quant": "CSI1000",
    }

    # Return and volatility characteristics per strategy
    strategy_params = {
        "stock_long": {"ret": (0.05, 0.20), "vol": (0.15, 0.28), "corr_market": 0.85},
        "market_neutral": {"ret": (0.04, 0.15), "vol": (0.05, 0.15), "corr_market": 0.15},
        "cta": {"ret": (0.05, 0.25), "vol": (0.12, 0.25), "corr_market": 0.0},
        "arbitrage": {"ret": (0.03, 0.10), "vol": (0.03, 0.08), "corr_market": 0.05},
        "macro_hedge": {"ret": (0.04, 0.18), "vol": (0.10, 0.20), "corr_market": 0.40},
        "bond": {"ret": (0.03, 0.08), "vol": (0.02, 0.06), "corr_market": 0.10},
        "multi_strategy": {"ret": (0.05, 0.15), "vol": (0.08, 0.18), "corr_market": 0.50},
        "fof": {"ret": (0.04, 0.12), "vol": (0.08, 0.15), "corr_market": 0.60},
        "quant": {"ret": (0.08, 0.25), "vol": (0.12, 0.22), "corr_market": 0.80},
    }

    funds = []
    nav_records = []
    fund_count = 0
    strategy_counts = {}
    inception_cursor = NAV_START_DATE

    for strategy in STRATEGIES:
        strat_count = strategy_counts.get(strategy, 0)
        names_list = fund_names.get(strategy, [f"基金{strategy}"])
        name = names_list[strat_count % len(names_list)]

        if isinstance(name, tuple):
            name = name[strat_count % len(name)]

        strategy_counts[strategy] = strat_count + 1
        fund_count += 1

        company = random.choice(companies)
        manager = random.choice(managers)
        benchmark = benchmarks.get(bm_map.get(strategy, "CSI300"))

        params = strategy_params[strategy]
        ann_ret = random.uniform(*params["ret"])
        ann_vol = random.uniform(*params["vol"])

        # Stagger inception dates
        inception_date = inception_cursor + timedelta(days=random.randint(0, 90))
        inception_cursor += timedelta(days=random.randint(0, 30))

        fund = Fund(
            company_id=company.id,
            manager_id=manager.id,
            name=name,
            code=f"FP{fund_count:04d}",
            strategy_type=strategy,
            inception_date=inception_date,
            status="active" if random.random() > 0.05 else "liquidated",
            aum=round(random.uniform(5000, 500000), 2),
            management_fee_rate=round(random.uniform(0.005, 0.02), 4),
            performance_fee_rate=round(random.uniform(0.15, 0.25), 4),
            performance_fee_benchmark="high_water_mark" if random.random() > 0.3 else "hurdle_rate",
            hurdle_rate=round(random.uniform(0.04, 0.06), 4),
            lockup_period_months=random.choice([0, 3, 6, 12]),
            subscription_frequency=random.choice(["daily", "weekly", "monthly"]),
            redemption_frequency=random.choice(["monthly", "quarterly"]),
            min_subscription_amount=1000000.0,
            benchmark_id=benchmark.id if benchmark else None,
            description=f"{name}是一个{strategy}策略的私募基金产品，由{company.name}管理。",
        )
        session.add(fund)
        funds.append(fund)

    session.flush()
    print(f"  Created {len(funds)} funds")

    # Generate NAV data for each fund
    print("  Generating NAV data...")
    total_nav = 0
    for i, fund in enumerate(funds):
        nav_series = generate_nav_series(
            fund.inception_date,
            NAV_END_DATE,
            initial_nav=1.0,
            annual_return=random.uniform(*strategy_params[fund.strategy_type]["ret"]),
            annual_vol=random.uniform(*strategy_params[fund.strategy_type]["vol"]),
        )

        for record in nav_series:
            nav_records.append({
                "fund_id": fund.id,
                "date": record["date"],
                "nav": record["nav"],
                "cumulative_nav": record["cumulative_nav"],
                "daily_return": record["daily_return"],
                "adjusted_nav": record["nav"],
                "dividend_amount": 0,
            })
            total_nav += 1

        if (i + 1) % 10 == 0:
            print(f"    NAV progress: {i + 1}/{len(funds)} funds, {total_nav} records so far")

    # Bulk insert NAV data
    print(f"  Inserting {len(nav_records)} NAV records...")
    batch_size = 5000
    for start in range(0, len(nav_records), batch_size):
        batch = nav_records[start : start + batch_size]
        session.execute(NavData.__table__.insert(), batch)
        if (start // batch_size) % 5 == 0:
            print(f"    Inserted {start + len(batch)}/{len(nav_records)}")
    session.flush()

    print(f"  Total NAV records: {len(nav_records)}")
    return funds


def create_benchmark_data(session: Session, benchmarks: dict[str, Benchmark]):
    """Generate synthetic benchmark data matching the fund NAV date range."""
    print("  Generating benchmark data...")
    total = 0

    bm_returns = {
        "CSI300": (0.06, 0.20),
        "CSI500": (0.08, 0.24),
        "CSI1000": (0.09, 0.26),
        "CBI": (0.035, 0.04),
        "NHCI": (0.05, 0.18),
    }

    for code, bm in benchmarks.items():
        ret, vol = bm_returns.get(code, (0.05, 0.15))
        series = generate_nav_series(NAV_START_DATE, NAV_END_DATE, 1000.0, ret, vol)
        records = []
        for record in series:
            records.append({
                "benchmark_id": bm.id,
                "date": record["date"],
                "value": record["nav"],
                "daily_return": record["daily_return"],
            })
            total += 1

        batch_size = 5000
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            session.execute(BenchmarkData.__table__.insert(), batch)
    session.flush()
    print(f"  Created {total} benchmark data records")


def main():
    engine = create_engine(settings.DATABASE_URL_SYNC, echo=False)

    # Create tables
    print("Dropping and recreating tables...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print("Tables created.")

    with Session(engine) as session:
        print("\n--- Seeding Companies ---")
        companies = create_companies(session)

        print("\n--- Seeding Managers ---")
        managers = create_managers(session, companies)

        print("\n--- Seeding Benchmarks ---")
        benchmarks = create_benchmarks(session)

        print("\n--- Seeding Funds + NAV Data ---")
        create_funds(session, companies, managers, benchmarks)

        print("\n--- Seeding Benchmark Data ---")
        create_benchmark_data(session, benchmarks)

        session.commit()
        print("\n✅ Seed data creation complete!")


if __name__ == "__main__":
    main()
