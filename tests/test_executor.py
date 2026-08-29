"""
Tests for core/execution/executor.

Note: the executor now takes an injectable client, so these tests pass a
fake client directly instead of patching a module-level global. That's
cleaner and means importing the module never touches the network.

current_inventory is passed explicitly and kept well within default
risk limits in tests that expect an order to succeed, so these tests
verify execution behavior specifically, not risk engine internals
(those are covered separately in test_risk_engine.py).
"""
from unittest.mock import MagicMock
from core.execution.executor import execute_signal, risk_check
from core.strategy.base import Signal


def test_hold_signal_does_not_place_order():
    fake_client = MagicMock()
    signal = Signal(action="hold", symbol="BTCUSDT", reason="stub — always holds")

    result = execute_signal(signal, quantity=0.001, current_inventory=0.0, client=fake_client)

    assert result is None
    fake_client.create_order.assert_not_called()


def test_buy_signal_places_order():
    fake_client = MagicMock()
    fake_client.create_order.return_value = {"orderId": 123, "status": "FILLED"}
    signal = Signal(action="buy", symbol="BTCUSDT", reason="test")

    result = execute_signal(signal, quantity=0.001, current_inventory=0.0, client=fake_client)

    assert result == {"orderId": 123, "status": "FILLED"}
    fake_client.create_order.assert_called_once_with(
        symbol="BTCUSDT",
        side="BUY",
        type="MARKET",
        quantity=0.001,
    )


def test_quantity_is_passed_through_not_hardcoded():
    """Guards against the previous hardcoded quantity=0.001."""
    fake_client = MagicMock()
    signal = Signal(action="buy", symbol="ETHUSDT", reason="test")

    execute_signal(signal, quantity=0.05, current_inventory=0.0, client=fake_client)

    assert fake_client.create_order.call_args.kwargs["quantity"] == 0.05


def test_order_blocked_when_risk_check_fails(monkeypatch):
    """Every order must pass the risk seam — architecture invariant."""
    fake_client = MagicMock()
    monkeypatch.setattr(
        "core.execution.executor.risk_check", lambda s, q, ci: False
    )
    signal = Signal(action="buy", symbol="BTCUSDT", reason="test")

    result = execute_signal(signal, quantity=0.001, current_inventory=0.0, client=fake_client)

    assert result is None
    fake_client.create_order.assert_not_called()


def test_order_failure_is_caught_and_returns_none():
    fake_client = MagicMock()
    fake_client.create_order.side_effect = Exception("insufficient balance")
    signal = Signal(action="buy", symbol="BTCUSDT", reason="test")

    result = execute_signal(signal, quantity=0.001, current_inventory=0.0, client=fake_client)

    assert result is None


def test_risk_check_allows_order_within_limits():
    """
    Replaces the old stub-era test — risk_check is no longer a no-op,
    this confirms a normal order within default limits is genuinely
    allowed through the real RiskEngine, not just trusted blindly.
    """
    signal = Signal(action="buy", symbol="BTCUSDT", reason="test")
    assert risk_check(signal, quantity=0.001, current_inventory=0.0) is True


def test_risk_check_blocks_order_exceeding_max_order_size():
    """
    New: confirms the real risk integration actually blocks an
    oversized order, not just a mocked-out risk_check. Uses a very
    large quantity to exceed the default MAX_ORDER_SIZE env-based limit.
    """
    signal = Signal(action="buy", symbol="BTCUSDT", reason="test")
    huge_quantity = 10_000_000.0
    assert risk_check(signal, quantity=huge_quantity, current_inventory=0.0) is False


def test_execute_signal_blocked_by_real_risk_engine_does_not_place_order():
    """
    End-to-end: an order that the real RiskEngine would reject (not a
    mocked risk_check) must not reach the exchange client at all.
    """
    fake_client = MagicMock()
    signal = Signal(action="buy", symbol="BTCUSDT", reason="test")
    huge_quantity = 10_000_000.0

    result = execute_signal(
        signal, quantity=huge_quantity, current_inventory=0.0, client=fake_client
    )

    assert result is None
    fake_client.create_order.assert_not_called()