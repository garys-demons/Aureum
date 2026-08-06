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


def scrub_sensitive_data(logger, method_name, event_dict):
    """Structlog processor: redact any key that looks sensitive."""
    for key in list(event_dict.keys()):
        if key.lower() in SENSITIVE_KEYS:
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