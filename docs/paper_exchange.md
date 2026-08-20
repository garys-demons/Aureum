# Paper Exchange — Reference

Plain-English explanation of `core/backtest/paper_exchange.py`.

## What it does
Simulates whether an order would have actually filled against real
historical order book data, and at what price — instead of assuming
every order fills instantly at the quoted price. This is what makes
backtest results meaningful rather than artificially optimistic.

## Market orders (`match_market_order`)
Walks price levels starting from the best price, consuming available
quantity at each level until the order is filled or the book runs out.

- If the top level doesn't have enough quantity, the order fills across
  multiple levels — this naturally produces **slippage**: the average
  fill price drifts worse than the best price whenever depth is thin.
- If the book can't cover the full requested quantity, the fill is
  **partial** (`fully_filled=False`), not silently completed. This is
  the direct fix for the "touch = fill" problem the architecture
  explicitly warns against — a real market order can't summon liquidity
  that isn't there.
- Charged at the **taker fee rate**, since a market order consumes
  existing liquidity rather than adding it.

## Limit orders (`match_limit_order`)
Same level-walking logic, but only considers price levels at least as
good as the limit price. Two key differences from a market order:

- **Never fills at a worse price than the limit** — if the book can't
  fill it within the limit, the order fills partially (or not at all)
  rather than "spilling over" into worse prices the way a market order
  would.
- Charged at the **maker fee rate**, since a limit order is treated as
  resting liquidity rather than immediately taking it.

## Fees
Two flat rates for now (`TAKER_FEE_RATE`, `MAKER_FEE_RATE`) — placeholders
pending confirmation of the real fee schedule (see Samarth's exchange
reference data from Phase 1's data-collection assignments). Fees are
calculated per fill: `quantity * average_fill_price * rate`.

## Slippage
Not modeled as a separate formula — it emerges naturally from walking
real order book depth level by level. A thinner book at the time of the
order produces more slippage automatically, matching real exchange
behavior.

## What this does NOT do
No portfolio/PnL tracking (Aryan's scope), no event ordering across a
full backtest run (Hansika's scope). This module only answers one
question: given a book and an order, what would honestly have happened.