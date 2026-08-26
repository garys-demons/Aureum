# Phase 6 — Kill-Switch Trigger Conditions

**Owner:** Hansika
**Status:** Trigger conditions defined, validated against real historical data

---

## Trigger 1: Order Book Gap / Reconciliation Failure

**Source:** Reuses existing, proven order-book reconciliation logic
(`services/market_data/order_book.py` `reconcile()`, live-wired in
`adapters/binance.py`) — not a separate detector, since this correctness
-critical logic already exists and is thoroughly tested (Phase 1/2).

**Condition:** Any order-book gap detected during live reconciliation.

**Rationale:** A gap means the book state was briefly wrong. Even one
occurrence is worth pausing on, since subsequent strategy decisions
based on a corrupted book are unreliable.

---

## Trigger 2: Reconnect Storm

**Source:** `core/persistence/anomaly.py` — `ReconnectFrequencyMonitor`
(existing, Phase 1)

**Condition:** 3+ reconnects within 60 seconds, on any single stream
(existing default, unchanged).

**Rationale:** Frequent reconnects on a supposedly-stable connection
signal real instability, independent of whether each individual
reconnect technically "succeeds."

---

## Trigger 3: Extreme Volatility (new, Phase 6)

**Source:** `core/persistence/volatility_anomaly.py` —
`ExtremeVolatilityMonitor` (new)

**Condition:** Price moves more than **2%** within a **60-second**
rolling window.

**Validated against real historical ADA data** (3 independent windows,
same data used in Phase 5's sensitivity analysis):

| Threshold | recent_24h | prior_24h | prior_48h |
|---|---|---|---|
| 1% | 0.14% | 0.07% | 0.49% |
| 2% (chosen) | 0.0% | 0.07% | 0.21% |
| 3% | 0.0% | 0.0% | 0.10% |

At 2%, trigger rate is near-zero on calm/moderately-trending windows
(recent_24h, prior_24h), and low but non-zero on the strongly trending
window (prior_48h, +21.98% over 48h per Phase 5 findings) — where it
correctly caught a genuine 9.78% move, among others. This is the
intended behavior: rare on normal conditions, responsive to real
volatility events.

**Window granularity note:** a 30-second window was also tested and
found to be structurally incompatible with 1-minute candle data — the
monitor needs 2+ observations within the window to measure a move, and
1-minute-interval candles can't provide 2 observations inside a
30-second lookback. Do not use a window shorter than roughly 2x the
underlying data's sampling interval.

---

## False-Positive Summary

Across all 3 tested windows and the chosen configuration
(2%/60s), volatility-trigger false-positive rate was **0.0%-0.21%** of
all candles — low enough that the trigger should not be "cried wolf"
territory, while still catching every genuinely large move observed
in the test data.

---

## Dependency

These triggers are defined and individually validated, but **not yet
wired into an actual kill switch mechanism** — that requires Samarth's
Phase 6 kill-switch implementation to exist first. Once available,
each trigger condition above will call into it directly.

## Reproduction

```
python -m research.download_sensitivity_windows
python -m research.validate_volatility_threshold
```