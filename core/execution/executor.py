# core/execution/executor.py
import os
import structlog
from dotenv import load_dotenv
from binance.client import Client
from core.strategy.base import Signal
from core.risk.risk_engine import RiskEngine
from core.risk.kill_switch import KillSwitch

load_dotenv()
log = structlog.get_logger()

# Shared module-level instance so the kill switch state persists across
# calls within a process - a fresh RiskEngine per call would silently
# reset kill-switch state every time, defeating its purpose.
_risk_engine = RiskEngine(
    kill_switch=KillSwitch(),
    max_order_size=float(os.getenv("MAX_ORDER_SIZE", "1000")),
    max_position=float(os.getenv("MAX_POSITION", "5000")),
)


def _build_client() -> Client:
    """Created lazily so importing this module doesn't hit the network."""
    return Client(
        api_key=os.getenv("BINANCE_TESTNET_API_KEY"),
        api_secret=os.getenv("BINANCE_TESTNET_API_SECRET"),
        testnet=True,
    )


def risk_check(signal: Signal, quantity: float, current_inventory: float) -> bool:
    """
    Real risk check (Phase 6) - every order MUST pass through here,
    architecture invariant. Delegates to core.risk.RiskEngine, which is
    fail-safe by design: any internal error defaults to reject.
    """
    allowed = _risk_engine.check(
        action=signal.action, quantity=quantity, current_inventory=current_inventory
    )
    log.debug(
        "risk_check_result",
        action=signal.action, symbol=signal.symbol, quantity=quantity,
        current_inventory=current_inventory, allowed=allowed,
    )
    return allowed


def execute_signal(
    signal: Signal, quantity: float, current_inventory: float, client: Client | None = None
):
    if signal.action == "hold":
        log.info("no_action", symbol=signal.symbol, reason=signal.reason)
        return None

    if not risk_check(signal, quantity, current_inventory):
        log.warning(
            "order_blocked_by_risk",
            symbol=signal.symbol, action=signal.action, quantity=quantity,
            current_inventory=current_inventory,
        )
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