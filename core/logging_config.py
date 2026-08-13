"""
core/logging_config.py — Structlog setup for Project Compass.

Call configure_logging() once, at process startup, in each entrypoint
that runs as its own process (services/market_data's runner,
services/trading's runner, apps/api, etc.)

Level rules (from the team working model doc):
    * connection events, reconciliation outcomes -> INFO
    * dedup drops                                -> DEBUG
    * unexpected exceptions                      -> ERROR, full traceback

Security rule, enforced in code (not just docs): known-sensitive field
names are redacted before any log line is rendered, so a stray
`log.info("order_submitted", api_secret=...)` anywhere in the codebase
can't leak a secret into logs or into core/persistence's audit trail.
"""

import logging
import os
import re
import sys

import structlog
from dotenv import load_dotenv

load_dotenv()  # picks up .env the same way the rest of the project does

# ---------------------------------------------------------------------
# Sensitive-field scrubbing
# ---------------------------------------------------------------------
# BINANCE_TESTNET_API_KEY / BINANCE_TESTNET_API_SECRET are the two real
# secret names in .env.example today. Keep this set a superset of what's
# actually used across the codebase — cheap to over-include, expensive
# to miss one.
SENSITIVE_KEYS = {
    "authorization",
    "auth_header",
    "api_key",
    "api_secret",
    "binance_testnet_api_key",
    "binance_testnet_api_secret",
    "database_url",  # contains a password in this project's connection string
    "secret",
    "signature",
    "password",
    "token",
}

_NON_ALNUM = re.compile(r"[^a-z0-9]")


def _normalize_key(key: str) -> str:
    """Lowercases and strips separators so 'api_key', 'apiKey', and
    'API-KEY' are all compared as the same thing: 'apikey'."""
    return _NON_ALNUM.sub("", key.lower())


# Precomputed once at import time, not per log call.
_NORMALIZED_PATTERNS = [_normalize_key(p) for p in SENSITIVE_KEYS]


def scrub_sensitive_data(logger, method_name, event_dict):
    """
    Structlog processor: redact any key whose name CONTAINS a sensitive
    pattern, ignoring case and separator style (_, -, camelCase all
    normalize the same way).

    Why substring + normalization, not exact match: a fixed set of
    exact key names misses real variants — "apiKey", "my_api_secret",
    "AUTH-TOKEN-2" would all have slipped through the old exact-match
    check (flagged in docs/risk_register.md, 2026-08-06). This catches
    all of those.

    Tradeoff, accepted deliberately: a field genuinely named something
    like "secretary_name" would also get redacted, since it contains
    "secret". Over-redacting a rare, harmless field is a much smaller
    problem than under-redacting a real credential — same "cheap to
    over-include, expensive to miss one" principle SENSITIVE_KEYS
    itself was built on.
    """
    for key in list(event_dict.keys()):
        normalized = _normalize_key(key)
        if any(pattern in normalized for pattern in _NORMALIZED_PATTERNS):
            event_dict[key] = "***REDACTED***"
    return event_dict


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
def configure_logging(json_logs: bool | None = None, log_level: str = "DEBUG") -> None:
    """
    Call once at service startup.

    json_logs: True  -> structured JSON (use this whenever logs need to
               be machine-read later, e.g. by anomaly detection).
               None  -> auto-detect from APP_ENV (defaults to "dev",
               which renders pretty console output instead).
    """
    if json_logs is None:
        json_logs = os.getenv("APP_ENV", "dev") != "dev"

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        scrub_sensitive_data,  # always runs, JSON or console
    ]

    if json_logs:
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[log_level]
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


if __name__ == "__main__":
    configure_logging(json_logs=False)
    log = structlog.get_logger("market_data")

    log.info("websocket_connected", exchange="binance_testnet", symbol="BTCUSDT")
    log.debug("duplicate_trade_dropped", trade_id="12345")
    log.info("order_submitted", order_id="abc123", api_secret="sk_live_supersecret")

    try:
        1 / 0
    except ZeroDivisionError:
        log.error("unexpected_exception", exc_info=True)