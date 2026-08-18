# Feature Engine — Reference

Plain-English explanation of every feature in `core/features/feature_engine.py`.
Formulas are also documented as docstrings in code; this is the human-readable version.

## Returns

**Simple returns** — percent change from one price to the next.
`(price_now - price_before) / price_before`

**Log returns** — natural-log version of the same idea, preferred in quant finance
because log returns can be added together across multiple time periods (simple
returns can't be added this way without distorting the result).
`ln(price_now / price_before)`

## Rolling Volatility

How much the price has been jumping around recently, not the direction — just the
"wildness." Computed as the standard deviation of returns over a sliding window
(e.g. the last 20 returns). Higher = more erratic price movement.

Uses *sample* standard deviation (divides by window size minus 1), the standard
convention for estimating volatility from a sample of returns.

**Alignment:** `result[i]` corresponds to the window *ending* at index 
`(i + window - 1)` in the input, not starting at index `i`. When aligning 
this output against a price/return series, offset by `(window - 1)` — 
otherwise a value gets attached to an earlier timestamp than the data it 
was actually computed from.

## RSI (Relative Strength Index)

Standard technical indicator, 0-100, answering: "lately, has the price been rising
more than falling?"
1. Split each price change into a gain (if positive) or a loss (if negative)
2. Average the gains and losses separately over the window
3. `RS = average_gain / average_loss`
4. `RSI = 100 - (100 / (1 + RS))`

Close to 100 = mostly rising recently. Close to 0 = mostly falling. Around 50 = balanced.

**Alignment:** `result[i]` corresponds to price-change index `(i + window - 1)`,
which is price index `(i + window)` — **not** `(i + window - 1)` in the original
price series, since price changes are already offset by 1 from prices (change[0]
is the difference between price[0] and price[1]). When aligning this output
against the original price series, offset by `window`, not `window - 1` —
otherwise a value gets attached to an earlier timestamp than the data it was
actually computed from. This differs slightly from Rolling Volatility's offset
because RSI operates on derived changes, not raw prices directly.

## Historical Spread

Same `spread()` formula from Phase 2 (ask price minus bid price), applied across a
list of historical order book snapshots instead of just the live one. No new math —
reuses `OrderBook.spread()` directly, once per historical snapshot.

## Historical Order-Book Imbalance

Same `order_book_imbalance()` formula from Phase 2 (ratio of bid-side size to total
size), applied across historical snapshots instead of just the live book. Reuses
the Phase 2 function directly.

## Look-ahead bias note

Every function here only uses data up to and including the point being measured —
never data from the future relative to that point. This matters because a feature
that accidentally "sees the future" would look correct in testing but produce
misleadingly good backtest results, since it's using information that wouldn't
have actually been available at the time.