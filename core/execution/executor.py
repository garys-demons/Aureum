# core/execution/executor.py
import os
import structlog
from dotenv import load_dotenv
from binance.client import Client
from core.strategy.base import Signal

load_dotenv()
log = structlog.get_logger()


def _build_client() -> Client:
    """Created lazily so importing this module doesn't hit the network."""
    return Client(
        api_key=os.getenv("BINANCE_TESTNET_API_KEY"),
        api_secret=os.getenv("BINANCE_TESTNET_API_SECRET"),
        testnet=True,
    )


def risk_check(signal: Signal, quantity: float) -> bool:
    """
    Placeholder for the risk engine (Phase 6).
    Every order MUST pass through here — architecture invariant.
    Returns True if the order is allowed.
    """
    log.debug("risk_check_stub", action=signal.action, symbol=signal.symbol, quantity=quantity)
    return True  # no-op until Phase 6


def execute_signal(signal: Signal, quantity: float, client: Client | None = None):
    if signal.action == "hold":
        log.info("no_action", symbol=signal.symbol, reason=signal.reason)
        return None

    if not risk_check(signal, quantity):
        log.warning("order_blocked_by_risk", symbol=signal.symbol, action=signal.action)
        return None

    client = client or _build_client()
    try:
        order = client.create_order(
            symbol=signal.symbol,
            side=signal.action.upper(),
            type="MARKET",
            quantity=quantity,
        )
        log.info("order_placed", symbol=signal.symbol, side=signal.action, quantity=quantity)
        return order
    except Exception as exc:
        log.error("order_failed", symbol=signal.symbol, error=str(exc), exc_info=True)
        return None