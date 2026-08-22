"""Quick check: is the loss explainable by fees alone, given the round-trip volume?"""
MAKER_FEE_RATE = 0.0005  # confirm against portfolio.py's actual constant
num_round_trips = 204  # from recent_24h run: num_closing_trades
avg_price = 0.20
avg_qty = 100.0
total_fee_drag = num_round_trips * 2 * avg_price * avg_qty * MAKER_FEE_RATE
print(f"Estimated total fee drag: ${total_fee_drag:.2f}")