# Backtest Results Dashboard — Scoping Note

Not built this phase (Phase 4 task explicitly says "not required this
phase, but worth scoping"). This is a plan to pick up later, not code.

## What exists to build against

`research/backtest/results.py`'s `save_backtest_run()` already
persists three queryable datasets per run, via `research/storage.py`:
- `<run_name>_trades` — full trade log
- `<run_name>_equity` — equity curve over time
- `<run_name>_summary` — final metrics (one row)

Anything built later reads these the same way any other page reads
data — `research.storage.load_dataset("results", ...)`.

## A reasonable shape for this page, when it gets built

Following the existing dashboard's pattern (`OrderBook.jsx`,
`Datasets.jsx` — same loading/error/empty-state style):

1. **A run picker** — list available runs (derived from
   `research.storage.list_datasets("results")`, deduped by run_name
   prefix)
2. **Summary cards** — the metrics from `<run_name>_summary`: total
   return, realized/unrealized PnL, win rate, max drawdown, trade
   count. Same `StatCard` pattern already used on the Order Book page.
3. **An equity curve chart** — the one genuinely new piece of UI this
   would need; nothing existing today plots a line chart. Worth
   picking a charting approach when this gets built, not guessing now.
4. **A trade log table** — same table pattern as `AuditLog.jsx`/
   `Datasets.jsx`.

## What this depends on that doesn't exist yet

- `apps/api` — still empty, same blocker every other dashboard page
  has. A `/api/backtest-runs` (or similar) endpoint would need to
  read from `research/storage.py` server-side and expose it over
  HTTP — the dashboard itself can't read local parquet files
  directly from the browser.
- At least one real completed backtest run to actually look at —
  depends on Hansika's engine and Gauri's paper exchange existing
  first.

## Recommendation

Revisit this once `apps/api` exists (a real blocker for every
dashboard page, not specific to this one) and at least one real
backtest run has been produced end-to-end. Building the UI before
either exists would mean guessing at a response shape twice — once
for this, once for whatever `apps/api` actually needs generally.