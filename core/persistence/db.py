"""
core/persistence/db.py — async SQLAlchemy engine + session factory.

Reads DATABASE_URL from .env (see .env.example) — either the shared
Timescale Cloud instance, or local Docker Postgres from
infra/docker/docker-compose.yml.

This module owns *connecting*. Table definitions live in models.py,
and read/write logic lives in repository.py — keeping these separate
means models.py can be imported (e.g. by Alembic) without needing a
live DB connection.
"""

import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL is None:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env and fill it in "
        "(see README.md 'Database' section — ask Samarth for the shared "
        "Timescale connection string, or point at local Docker Postgres)."
    )

# echo=False by default — flip to True locally if you need to see the raw
# SQL SQLAlchemy is generating, but don't merge that on.
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# expire_on_commit=False: we generally read committed data back out for
# logging/debugging right after writing it, so avoid the extra round trip
# SQLAlchemy would otherwise do to refresh objects post-commit.
AsyncSessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession
)


async def get_session() -> AsyncSession:
    """
    Usage:
        async with AsyncSessionLocal() as session:
            ...

    This helper exists mainly for FastAPI-style dependency injection in
    apps/api later; for scripts and services, just use AsyncSessionLocal()
    directly as an async context manager.
    """
    async with AsyncSessionLocal() as session:
        yield session