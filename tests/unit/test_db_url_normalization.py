"""
tests/unit/test_db_url_normalization.py

Regression tests for docs/risk_register.md (2026-08-08): getting the
real shared Timescale connection string working required three
separate, manual .env edits, each failing with a different cryptic
error (NoSuchModuleError, then a asyncpg TypeError about 'sslmode').
_normalize_database_url() fixes all three automatically so nobody else
has to rediscover them by hand.
"""

from core.persistence.db import _normalize_database_url


def test_normalizes_plain_postgres_scheme():
    result = _normalize_database_url(
        "postgres://user:pass@host:5432/db?sslmode=require"
    )
    assert result == "postgresql+asyncpg://user:pass@host:5432/db?ssl=require"


def test_normalizes_postgresql_without_driver():
    result = _normalize_database_url(
        "postgresql://user:pass@host:5432/db?sslmode=require"
    )
    assert result == "postgresql+asyncpg://user:pass@host:5432/db?ssl=require"


def test_normalizes_wrong_driver_prefix():
    """"postgres+asyncpg" (base name wrong, but already has a driver
    suffix) is a real variant someone could type by half-fixing the URL
    themselves — must still get corrected to "postgresql+asyncpg"."""
    result = _normalize_database_url(
        "postgres+asyncpg://user:pass@host:5432/db?sslmode=require"
    )
    assert result == "postgresql+asyncpg://user:pass@host:5432/db?ssl=require"


def test_already_correct_url_passes_through_unchanged():
    url = "postgresql+asyncpg://user:pass@host:5432/db?ssl=require"
    assert _normalize_database_url(url) == url


def test_url_without_query_params_still_works():
    result = _normalize_database_url("postgres://user:pass@host:5432/db")
    assert result == "postgresql+asyncpg://user:pass@host:5432/db"


def test_non_postgres_urls_are_left_completely_untouched():
    """
    Critical: round-tripping some URLs (notably sqlite's) through
    urlsplit/urlunsplit silently corrupts them (drops a slash). Only
    postgres/postgresql URLs should ever be touched.
    """
    sqlite_url = "sqlite+aiosqlite:///:memory:"
    assert _normalize_database_url(sqlite_url) == sqlite_url