"""
Position size limits — Phase 6. Two independent checks:
1. Max position size: would this order push total inventory too far?
2. Max order size: is this single order too large, regardless of
   current inventory?
Fail-safe: any exception during checking should be treated as a
rejection, never silently allowed through (see risk_engine.py).
"""


def exceeds_max_order_size(quantity: float, max_order_size: float) -> bool:
    return abs(quantity) > max_order_size


def exceeds_max_position(
    current_inventory: float, order_quantity: float, action: str, max_position: float
) -> bool:
    """
    Projects what inventory WOULD be after this order fills, and checks
    if that projected value exceeds the limit - not just checking
    current inventory, since the whole point is to catch the order
    that would push it over the edge.
    """
    if action == "buy":
        projected = current_inventory + order_quantity
    elif action == "sell":
        projected = current_inventory - order_quantity
    else:
        return False  # "hold" can't affect position

    return abs(projected) > max_position