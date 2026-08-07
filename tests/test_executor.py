from unittest.mock import patch, MagicMock
from core.strategy.base import Signal
from core.execution.executor import execute_signal


def test_hold_signal_does_not_place_order():
    signal = Signal(action="hold", symbol="BTCUSDT", reason="stub — always holds")
    result = execute_signal(signal)
    assert result is None


@patch("core.execution.executor.client")
def test_buy_signal_places_order(mock_client):
    mock_client.create_order.return_value = {"status": "FILLED"}
    signal = Signal(action="buy", symbol="BTCUSDT", reason="test buy")
    result = execute_signal(signal)
    assert result["status"] == "FILLED"
    mock_client.create_order.assert_called_once()