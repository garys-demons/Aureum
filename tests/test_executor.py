"""
Tests for core/execution/executor.

Note: the executor now takes an injectable client, so these tests pass a
fake client directly instead of patching a module-level global. That's
cleaner and means importing the module never touches the network.
"""
from unittest.mock import MagicMock

from core.execution.executor import execute_signal, risk_check
from core.strategy.base import Signal


def test_hold_signal_does_not_place_order():
    fake_client = MagicMock()
    signal = Signal(action="hold", symbol="BTCUSDT", reason="stub — always holds")

    result = execute_signal(signal, quantity=0.001, client=fake_client)

    assert result is None
    fake_client.create_order.assert_not_called()


def test_buy_signal_places_order():
    fake_client = MagicMock()
    fake_client.create_order.return_value = {"orderId": 123, "status": "FILLED"}
    signal = Signal(action="buy", symbol="BTCUSDT", reason="test")

    result = execute_signal(signal, quantity=0.001, client=fake_client)

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

    execute_signal(signal, quantity=0.05, client=fake_client)

    assert fake_client.create_order.call_args.kwargs["quantity"] == 0.05


def test_order_blocked_when_risk_check_fails(monkeypatch):
    """Every order must pass the risk seam — architecture invariant."""
    fake_client = MagicMock()
    monkeypatch.setattr("core.execution.executor.risk_check", lambda s, q: False)
    signal = Signal(action="buy", symbol="BTCUSDT", reason="test")

    result = execute_signal(signal, quantity=0.001, client=fake_client)

    assert result is None
    fake_client.create_order.assert_not_called()


def test_order_failure_is_caught_and_returns_none():
    fake_client = MagicMock()
    fake_client.create_order.side_effect = Exception("insufficient balance")
    signal = Signal(action="buy", symbol="BTCUSDT", reason="test")

    result = execute_signal(signal, quantity=0.001, client=fake_client)

    assert result is None


def test_risk_check_stub_currently_allows_orders():
    """Documents that risk_check is a no-op until Phase 6."""
    signal = Signal(action="buy", symbol="BTCUSDT", reason="test")
    assert risk_check(signal, 0.001) is True