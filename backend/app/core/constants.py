"""Enums and constants used across the application."""

from enum import Enum


class StrategyType(str, Enum):
    STOCK_LONG = "stock_long"
    MARKET_NEUTRAL = "market_neutral"
    CTA = "cta"
    ARBITRAGE = "arbitrage"
    MACRO_HEDGE = "macro_hedge"
    BOND = "bond"
    MULTI_STRATEGY = "multi_strategy"
    FOF = "fof"
    QUANT = "quant"
    OTHER = "other"

    @classmethod
    def labels(cls) -> dict:
        return {
            cls.STOCK_LONG: "股票多头",
            cls.MARKET_NEUTRAL: "市场中性",
            cls.CTA: "CTA",
            cls.ARBITRAGE: "套利",
            cls.MACRO_HEDGE: "宏观对冲",
            cls.BOND: "债券",
            cls.MULTI_STRATEGY: "多策略",
            cls.FOF: "FOF",
            cls.QUANT: "量化",
            cls.OTHER: "其他",
        }


class FundStatus(str, Enum):
    ACTIVE = "active"
    LIQUIDATED = "liquidated"
    SUSPENDED = "suspended"
    PRE_ISSUE = "pre_issue"

    @classmethod
    def labels(cls) -> dict:
        return {
            cls.ACTIVE: "运行中",
            cls.LIQUIDATED: "已清盘",
            cls.SUSPENDED: "暂停申购",
            cls.PRE_ISSUE: "待发行",
        }


class CompanyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEREGISTERED = "deregistered"

    @classmethod
    def labels(cls) -> dict:
        return {
            cls.ACTIVE: "正常运营",
            cls.INACTIVE: "非活跃",
            cls.DEREGISTERED: "已注销",
        }


class PeriodType(str, Enum):
    MTD = "MTD"        # Month to date
    QTD = "QTD"        # Quarter to date
    YTD = "YTD"        # Year to date
    M1 = "1M"
    M3 = "3M"
    M6 = "6M"
    Y1 = "1Y"
    Y3 = "3Y"
    Y5 = "5Y"
    SI = "SI"          # Since inception

    @classmethod
    def labels(cls) -> dict:
        return {
            cls.MTD: "本月以来",
            cls.QTD: "本季以来",
            cls.YTD: "今年以来",
            cls.M1: "近1月",
            cls.M3: "近3月",
            cls.M6: "近6月",
            cls.Y1: "近1年",
            cls.Y3: "近3年",
            cls.Y5: "近5年",
            cls.SI: "成立以来",
        }


class ImportType(str, Enum):
    NAV_DATA = "nav_data"
    FUND_LIST = "fund_list"
    BENCHMARK = "benchmark"


class ImportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ReportType(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    CUSTOM = "custom"


TRADING_DAYS_PER_YEAR = 252
