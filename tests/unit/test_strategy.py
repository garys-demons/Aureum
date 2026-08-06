from core.strategy.stub_strategy import StubStrategy


def test_stub_strategy_returns_hold():
    strategy = StubStrategy()
    signal = strategy.decide({"symbol": "BTCUSDT", "price": 65000})
    assert signal.action == "hold"
    assert signal.symbol == "BTCUSDT"