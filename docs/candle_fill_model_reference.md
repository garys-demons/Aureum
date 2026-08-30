# Candle-Close Fill Model — Reference

**This is an approximation, not a realistic fill simulation.** Used only for
symbols where real order-book depth doesn't exist yet (currently: ADA
baseline). For any symbol with real order-book data, use
`match_market_order`/`match_limit_order` (`core/backtest/paper_exchange.py`)
instead — those are the actual depth-based fill simulation.

## Market orders
Fills the full requested quantity at candle close, adjusted by a flat
documented slippage assumption (`MARKET_ORDER_SLIPPAGE`, currently 0.05%)
— worse than close for the trader in both directions (buys fill above
close, sells fill below close).

## Limit orders
Fills at the limit price only if the candle's high/low range shows the
price actually traded there — a buy limit fills if the candle's low
reached at or below it; a sell limit fills if the candle's high reached
at or above it. Otherwise, no fill.

## Known limitations (deliberately not hidden)
- **No partial fills** — every fill is for the full requested quantity,
  regardless of size. A real order could easily be larger than actual
  available liquidity at that candle; this model has no way to detect
  or represent that.
- **Slippage is a flat assumption**, not derived from real depth — it
  does not reflect how much a specific order size would actually move
  the market.
- **Limit fills are candle-range-based**, coarser than tick-level or
  order-book-level reality — a candle's low touching the limit doesn't
  guarantee enough size was available there to fill a large order.

## When to stop using this
Once real order-book data exists for a symbol (matching how BTC was
captured), switch that symbol's backtests to
`match_market_order`/`match_limit_order`. This model exists to unblock
evaluation in the meantime, not as a permanent substitute.