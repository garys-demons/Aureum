"""Unit tests for TradeDeduplicator (TRD Section 7)."""
from services.market_data.dedup import TradeDeduplicator
from services.market_data.models import TradeEvent


def make_trade(trade_id: int, symbol: str = "BTCUSDT") -> TradeEvent:
    return TradeEvent(
        event_type="trade",
        exchange="binance",
        symbol=symbol,
        event_time=1,
        received_time=1,
        trade_id=trade_id,
        price=100,
        quantity=1,
        buyer_maker=True,
        trade_time=1,
    )


def test_first_occurrence_is_not_duplicate():
    dedup = TradeDeduplicator()
    trade = make_trade(1)
    assert dedup.is_duplicate(trade) is False


def test_second_occurrence_is_duplicate():
    dedup = TradeDeduplicator()
    trade = make_trade(1)
    dedup.mark_seen(trade)
    assert dedup.is_duplicate(trade) is True


def test_different_trade_ids_are_not_duplicates():
    dedup = TradeDeduplicator()
    dedup.mark_seen(make_trade(1))
    assert dedup.is_duplicate(make_trade(2)) is False


def test_same_trade_id_different_symbol_is_not_duplicate():
    dedup = TradeDeduplicator()
    dedup.mark_seen(make_trade(1, symbol="BTCUSDT"))
    assert dedup.is_duplicate(make_trade(1, symbol="ETHUSDT")) is False


def test_cache_evicts_oldest_when_over_capacity():
    dedup = TradeDeduplicator(max_size=2)
    dedup.mark_seen(make_trade(1))
    dedup.mark_seen(make_trade(2))
    dedup.mark_seen(make_trade(3))
    assert dedup.is_duplicate(make_trade(1)) is False
    assert dedup.is_duplicate(make_trade(3)) is True
