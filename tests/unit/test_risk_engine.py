from cmath import log
from unittest.mock import MagicMock
from core.risk.risk_engine import RiskEngine
from core.risk.kill_switch import KillSwitch, TriggerCategory


def make_engine(max_order_size=1000, max_position=1000):
    return RiskEngine(KillSwitch(), max_order_size=max_order_size, max_position=max_position)


def test_hold_always_allowed():
    engine = make_engine()
    assert engine.check("hold", quantity=0, current_inventory=0) is True


def test_normal_order_within_limits_allowed():
    engine = make_engine()
    assert engine.check("buy", quantity=100, current_inventory=0) is True


def test_order_exceeding_max_size_rejected():
    engine = make_engine(max_order_size=50)
    assert engine.check("buy", quantity=100, current_inventory=0) is False


def test_order_exceeding_position_limit_rejected():
    engine = make_engine(max_position=500)
    assert engine.check("buy", quantity=100, current_inventory=450) is False


def test_kill_switch_active_blocks_everything():
    ks = KillSwitch()
    ks.trigger(TriggerCategory.EXTREME_VOLATILITY, "test")
    engine = RiskEngine(ks, max_order_size=1000, max_position=1000)

    assert engine.check("buy", quantity=1, current_inventory=0) is False


def test_unexpected_exception_blocks_not_allows():
    """
    THE fail-safe test. If checking itself breaks, the engine must
    still return False, never True and never raise.
    """
    engine = make_engine()
    broken_kill_switch = MagicMock()
    broken_kill_switch.is_active = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
    engine.kill_switch = broken_kill_switch

    result = engine.check("buy", quantity=100, current_inventory=0)
    assert result is False  # not True, and no exception propagated

def test_logging_failure_inside_except_does_not_crash_check():
    """
    If the logging call itself fails while handling an unexpected
    exception, check() must still return False, not raise - the
    fail-safe guarantee can't depend on logging always succeeding.
    """
    from unittest.mock import patch
    from core.risk.kill_switch import KillSwitch
    from core.risk.risk_engine import RiskEngine

    engine = RiskEngine(kill_switch=KillSwitch(), max_order_size=100, max_position=1000)

    with patch("core.risk.risk_engine.exceeds_max_order_size", side_effect=RuntimeError("boom")):
        with patch("core.risk.risk_engine.log.error", side_effect=Exception("logging broke")):
            result = engine.check(action="buy", quantity=10, current_inventory=0)
            assert result is False