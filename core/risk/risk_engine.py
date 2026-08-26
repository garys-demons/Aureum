"""
RiskEngine — Phase 6. The single entry point risk_check() in the
executor calls into. Combines the kill switch and position limits.

FAIL-SAFE RULE: if this engine cannot determine whether an order is
safe (an unexpected exception, missing data), the default is REJECT,
never allow. This is the one rule that matters most in this whole
module - see test_risk_engine.py::test_unexpected_exception_blocks_not_allows.
"""
import structlog

from core.risk.kill_switch import KillSwitch, TriggerCategory
from core.risk.position_limits import exceeds_max_order_size, exceeds_max_position

log = structlog.get_logger()


class RiskEngine:
    def __init__(
        self,
        kill_switch: KillSwitch,
        max_order_size: float,
        max_position: float,
    ):
        self.kill_switch = kill_switch
        self.max_order_size = max_order_size
        self.max_position = max_position

    def check(self, action: str, quantity: float, current_inventory: float) -> bool:
        """
        Returns True if the order is allowed, False if it should be
        blocked. Never raises - any internal error is caught and
        treated as a rejection (fail-safe).
        """
        try:
            if self.kill_switch.is_active:
                log.warning("risk_rejected_kill_switch_active", **self.kill_switch.status())
                return False

            if action == "hold":
                return True

            if exceeds_max_order_size(quantity, self.max_order_size):
                log.warning("risk_rejected_order_too_large", quantity=quantity, max=self.max_order_size)
                return False

            if exceeds_max_position(current_inventory, quantity, action, self.max_position):
                log.warning(
                    "risk_rejected_position_limit",
                    current_inventory=current_inventory, quantity=quantity, action=action,
                )
                return False

            return True

        except Exception as e:
            # Fail-safe: cannot determine safety -> reject, do not allow.
            # Logging itself is wrapped separately - a logging failure must
            # never prevent this fail-safe return from happening.
            try:
                log.error("risk_check_error_defaulting_to_reject", error=str(e), exc_info=True)
            except Exception:
                pass
            return False