"""initial: all tables

Revision ID: 001
Revises:
Create Date: 2026-05-30
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # fund_companies
    op.create_table(
        "fund_companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("short_name", sa.String(100)),
        sa.Column("registration_code", sa.String(100), unique=True),
        sa.Column("registration_date", sa.Date()),
        sa.Column("total_aum", sa.Numeric(18, 2)),
        sa.Column("founding_date", sa.Date()),
        sa.Column("province", sa.String(50)),
        sa.Column("city", sa.String(50)),
        sa.Column("website", sa.String(255)),
        sa.Column("contact_info", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # fund_managers
    op.create_table(
        "fund_managers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fund_companies.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("title", sa.String(100)),
        sa.Column("experience_years", sa.Numeric(4, 1)),
        sa.Column("education", sa.String(255)),
        sa.Column("certifications", sa.Text()),
        sa.Column("bio", sa.Text()),
        sa.Column("photo_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # benchmarks
    op.create_table(
        "benchmarks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), unique=True),
        sa.Column("category", sa.String(50)),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # funds
    op.create_table(
        "funds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fund_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fund_managers.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(100), unique=True),
        sa.Column("strategy_type", sa.String(50), nullable=False),
        sa.Column("inception_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("aum", sa.Numeric(18, 2)),
        sa.Column("management_fee_rate", sa.Numeric(5, 4)),
        sa.Column("performance_fee_rate", sa.Numeric(5, 4)),
        sa.Column("performance_fee_benchmark", sa.String(50)),
        sa.Column("hurdle_rate", sa.Numeric(5, 4)),
        sa.Column("lockup_period_months", sa.Integer(), server_default="0"),
        sa.Column("subscription_frequency", sa.String(20)),
        sa.Column("redemption_frequency", sa.String(20)),
        sa.Column("min_subscription_amount", sa.Numeric(18, 2)),
        sa.Column("benchmark_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("benchmarks.id", ondelete="SET NULL")),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # nav_data
    op.create_table(
        "nav_data",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("fund_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("funds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("nav", sa.Numeric(12, 6), nullable=False),
        sa.Column("cumulative_nav", sa.Numeric(12, 6)),
        sa.Column("daily_return", sa.Numeric(12, 8)),
        sa.Column("adjusted_nav", sa.Numeric(12, 6)),
        sa.Column("dividend_amount", sa.Numeric(12, 6), server_default="0"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("fund_id", "date", name="uq_fund_date"),
    )
    op.create_index("idx_nav_fund_date", "nav_data", ["fund_id", sa.text("date DESC")])
    op.create_index("idx_nav_date", "nav_data", ["date"])
    op.create_index("idx_nav_fund_return", "nav_data", ["fund_id", "daily_return"])

    # benchmark_data
    op.create_table(
        "benchmark_data",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("benchmark_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("benchmarks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(15, 4), nullable=False),
        sa.Column("daily_return", sa.Numeric(12, 8)),
        sa.UniqueConstraint("benchmark_id", "date", name="uq_benchmark_date"),
    )
    op.create_index("idx_benchmark_date", "benchmark_data", ["benchmark_id", sa.text("date DESC")])

    # performance_metrics
    op.create_table(
        "performance_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("fund_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("funds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_type", sa.String(10), nullable=False),
        sa.Column("calculation_date", sa.Date(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        # Return metrics
        sa.Column("cumulative_return", sa.Numeric(15, 8)),
        sa.Column("annualized_return", sa.Numeric(15, 8)),
        sa.Column("monthly_returns", postgresql.JSONB()),
        sa.Column("best_month_return", sa.Numeric(15, 8)),
        sa.Column("worst_month_return", sa.Numeric(15, 8)),
        # Risk metrics
        sa.Column("annualized_volatility", sa.Numeric(15, 8)),
        sa.Column("max_drawdown", sa.Numeric(15, 8)),
        sa.Column("max_drawdown_start_date", sa.Date()),
        sa.Column("max_drawdown_end_date", sa.Date()),
        sa.Column("max_drawdown_recovery_date", sa.Date()),
        sa.Column("downside_deviation", sa.Numeric(15, 8)),
        sa.Column("var_95", sa.Numeric(15, 8)),
        sa.Column("var_99", sa.Numeric(15, 8)),
        sa.Column("cvar_95", sa.Numeric(15, 8)),
        # Risk-adjusted metrics
        sa.Column("sharpe_ratio", sa.Numeric(10, 6)),
        sa.Column("sortino_ratio", sa.Numeric(10, 6)),
        sa.Column("calmar_ratio", sa.Numeric(10, 6)),
        sa.Column("information_ratio", sa.Numeric(10, 6)),
        sa.Column("treynor_ratio", sa.Numeric(10, 6)),
        # Other statistics
        sa.Column("win_rate", sa.Numeric(8, 6)),
        sa.Column("profit_loss_ratio", sa.Numeric(10, 6)),
        sa.Column("alpha", sa.Numeric(15, 8)),
        sa.Column("beta", sa.Numeric(10, 6)),
        sa.Column("correlation", sa.Numeric(10, 6)),
        sa.Column("tracking_error", sa.Numeric(15, 8)),
        sa.Column("skewness", sa.Numeric(10, 6)),
        sa.Column("kurtosis", sa.Numeric(10, 6)),
        sa.Column("positive_days", sa.Integer()),
        sa.Column("negative_days", sa.Integer()),
        sa.Column("total_days", sa.Integer()),
        sa.Column("rolling_metrics", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("fund_id", "period_type", "calculation_date", name="uq_fund_period_date"),
    )
    op.create_index("idx_pm_fund_period", "performance_metrics", ["fund_id", "period_type", sa.text("calculation_date DESC")])

    # import_jobs
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(100)),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("import_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("total_rows", sa.Integer()),
        sa.Column("success_rows", sa.Integer(), server_default="0"),
        sa.Column("error_rows", sa.Integer(), server_default="0"),
        sa.Column("error_details", postgresql.JSONB()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # report_templates
    op.create_table(
        "report_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # generated_reports
    op.create_table(
        "generated_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("report_templates.id")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("file_path", sa.String(1000)),
        sa.Column("file_type", sa.String(10)),
        sa.Column("file_size_bytes", sa.BigInteger()),
        sa.Column("status", sa.String(20), server_default="generating"),
        sa.Column("parameters", postgresql.JSONB()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("generated_reports")
    op.drop_table("report_templates")
    op.drop_table("import_jobs")
    op.drop_index("idx_pm_fund_period", table_name="performance_metrics")
    op.drop_table("performance_metrics")
    op.drop_index("idx_benchmark_date", table_name="benchmark_data")
    op.drop_table("benchmark_data")
    op.drop_index("idx_nav_fund_return", table_name="nav_data")
    op.drop_index("idx_nav_date", table_name="nav_data")
    op.drop_index("idx_nav_fund_date", table_name="nav_data")
    op.drop_table("nav_data")
    op.drop_table("funds")
    op.drop_table("benchmarks")
    op.drop_table("fund_managers")
    op.drop_table("fund_companies")
