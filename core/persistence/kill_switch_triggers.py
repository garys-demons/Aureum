"""
core/persistence/kill_switch_triggers.py — wires Hansika's trigger
conditions (Phase 6) into Samarth's KillSwitch.

Each function here wraps an existing detector and, on detection, calls
kill_switch.trigger() with the matching TriggerCategory. Kept separate
from the detectors themselves (anomaly.py, volatility_anomaly.py) so
those stay simple and don't need to know about the kill switch to be
unit-tested in isolation.

Imports core.risk.kill_switch.KillSwitch / TriggerCategory directly -
confirmed real interface (Phase 6, feature/risk-engine).
"""
from core.persistence.anomaly import ReconnectFrequencyMonitor
from core.persistence.volatility_anomaly import ExtremeVolatilityMonitor

from core.risk.kill_switch import KillSwitch, TriggerCategory


def check_order_book_gap(kill_switch, gap_detected: bool, stream_key: str) -> None:
    """
    Call this wherever an order-book gap is detected (existing
    reconciliation logic in services/market_data/order_book.py /
    adapters/binance.py). Triggers the kill switch on any gap.
    """
    if gap_detected:
        kill_switch.trigger(
            category=TriggerCategory.ORDER_BOOK_GAP,
            reason=f"Order book gap detected on {stream_key}",
        )


def check_reconnect_storm(
    kill_switch,
    monitor: ReconnectFrequencyMonitor,
    stream_key: str,
) -> bool:
    """
    Call this on every reconnect event. Returns the monitor's own
    detection result (for logging/testing) and triggers the kill
    switch if the reconnect frequency threshold was exceeded.
    """
    exceeded = monitor.record_reconnect(stream_key)
    if exceeded:
        kill_switch.trigger(
            category=TriggerCategory.RECONNECT_STORM,
            reason=(
                f"Reconnect frequency exceeded on {stream_key}: "
                f">{monitor.max_reconnects} reconnects within {monitor.window_seconds}s"
            ),
        )
    return exceeded


def check_extreme_volatility(
    kill_switch,
    monitor: ExtremeVolatilityMonitor,
    symbol: str,
    price: float,
) -> bool:
    """
    Call this on every new price observation. Returns the monitor's own
    detection result (for logging/testing) and triggers the kill
    switch if the price move exceeded the configured threshold.
    """
    exceeded = monitor.observe(symbol, price)
    if exceeded:
        kill_switch.trigger(
            category=TriggerCategory.EXTREME_VOLATILITY,
            reason=(
                f"Extreme volatility on {symbol}: moved more than "
                f"{monitor.max_pct_move:.1%} within {monitor.window_seconds}s"
            ),
        )
    return exceeded