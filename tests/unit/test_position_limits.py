from core.risk.position_limits import exceeds_max_order_size, exceeds_max_position


def test_order_within_max_size_is_allowed():
    assert exceeds_max_order_size(quantity=50, max_order_size=100) is False


def test_order_exceeding_max_size_is_rejected():
    assert exceeds_max_order_size(quantity=150, max_order_size=100) is True


def test_order_at_exact_max_size_is_allowed():
    assert exceeds_max_order_size(quantity=100, max_order_size=100) is False


def test_buy_that_stays_within_position_limit_is_allowed():
    # current 300, +100 = 400, limit 500 -> fine
    assert exceeds_max_position(300, 100, "buy", max_position=500) is False


def test_buy_that_would_exceed_position_limit_is_rejected():
    # current 450, +100 = 550, limit 500 -> exceeds
    assert exceeds_max_position(450, 100, "buy", max_position=500) is True


def test_sell_that_would_exceed_short_limit_is_rejected():
    # current -450, -100 = -550, |-550| = 550 > 500 -> exceeds
    assert exceeds_max_position(-450, 100, "sell", max_position=500) is True


def test_sell_that_reduces_position_is_allowed():
    # current 450, sell 100 -> 350, within limit
    assert exceeds_max_position(450, 100, "sell", max_position=500) is False


def test_hold_never_exceeds():
    assert exceeds_max_position(1000, 100, "hold", max_position=500) is False