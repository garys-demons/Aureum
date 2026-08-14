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
from typing import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()


def _normalize_database_url(url: str) -> str:
    """
    Normalizes connection-string variations that otherwise fail with
    three different, unhelpful errors (docs/risk_register.md,
    2026-08-08 entry — hit for real getting the shared Timescale URL
    working):

      1. "postgres://" or "postgresql://" -> "postgresql+asyncpg://"
         (asyncpg is the driver this project actually uses; SQLAlchemy
         needs the "+asyncpg" to know that)
      2. "?sslmode=require" -> "?ssl=require"
         (sslmode is the libpq/psql parameter name; asyncpg's driver
         expects "ssl" instead — same setting, different name)

    Only touches postgres/postgresql URLs — anything else (e.g. the
    sqlite+aiosqlite URLs tests use) passes through completely
    unchanged. This matters: round-tripping a sqlite URL through
    urlsplit/urlunsplit silently drops a slash ("sqlite:///x" becomes
    "sqlite:/x"), so it's not safe to rewrite every URL unconditionally
    — only the schemes that actually need fixing.
    """
    scheme = url.split("://", 1)[0]
    base_scheme = scheme.split("+", 1)[0]  # strips any existing "+driver" suffix
    if base_scheme not in ("postgres", "postgresql"):
        return url

    _, netloc, path, query, fragment = urlsplit(url)

    query_params = dict(parse_qsl(query))
    if "sslmode" in query_params:
        query_params["ssl"] = query_params.pop("sslmode")
    query = urlencode(query_params)

    return urlunsplit(("postgresql+asyncpg", netloc, path, query, fragment))


DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL is None:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env and fill it in "
        "(see README.md 'Database' section — ask Samarth for the shared "
        "Timescale connection string, or point at local Docker Postgres)."
    )

DATABASE_URL = _normalize_database_url(DATABASE_URL)

# echo=False by default — flip to True locally if you need to see the raw
# SQL SQLAlchemy is generating, but don't merge that on.
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# expire_on_commit=False: we generally read committed data back out for
# logging/debugging right after writing it, so avoid the extra round trip
# SQLAlchemy would otherwise do to refresh objects post-commit.
AsyncSessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
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