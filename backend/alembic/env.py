"""Alembic environment configuration."""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add the backend directory to sys.path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import all models so Alembic can detect them
from app.database import Base
from app.domains.companies.models import FundCompany
from app.domains.managers.models import FundManager
from app.domains.funds.models import Fund
from app.domains.nav.models import NavData
from app.domains.metrics.models import PerformanceMetric
from app.domains.benchmarks.models import Benchmark, BenchmarkData
from app.domains.import_export.models import ImportJob
from app.domains.reports.models import ReportTemplate, GeneratedReport

# Alembic Config object
config = context.config

# Set up logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode (emit SQL without connecting)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode (connect to DB and execute)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
