"""
DocuBot — Alembic env.py async (asyncpg).
Las extensiones PostgreSQL se instalan con una conexión AUTOCOMMIT separada.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings
from app.db.session import Base
import app.db.models  # noqa: F401

config = context.config

# ── URL con driver asyncpg ─────────────────────────────────────────────
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # ── Paso 1: instalar extensiones con engine AUTOCOMMIT dedicado ────
    autocommit_engine = create_async_engine(db_url, isolation_level="AUTOCOMMIT", poolclass=pool.NullPool)
    async with autocommit_engine.connect() as conn:
        for ext in ["uuid-ossp", "vector", "pg_trgm"]:
            try:
                await conn.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{ext}"'))
                print(f"[migrations] Extension '{ext}' OK")
            except Exception as e:
                print(f"[migrations] Extension '{ext}' warning: {e}")
    await autocommit_engine.dispose()

    # ── Paso 2: correr migraciones con engine normal ───────────────────
    engine = create_async_engine(db_url, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
