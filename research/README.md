# research/

This is the research environment — where historical data, computed
features, and exploratory analysis live for Phase 3 onward.

## The one rule that matters most

**Nothing in `research/` is ever imported by `core/` or `services/`.**
This is the live trading pipeline's boundary — research code can be
messy, exploratory, and iterate fast, precisely because it never has
to be production-safe. The moment something here needs to run live,
it gets rewritten properly in `core/` or `services/`, not imported
from here.

This boundary is checked automatically:
`tests/unit/test_research_boundary.py` scans `core/` and `services/`
for any import mentioning `research` and fails the build if it finds
one.

## Structure

`data/raw/` and `data/processed/` already existed as gitignored paths
in `.gitignore` before this task — that convention is followed here
rather than inventing a separate `research/data/` location.
`data/results/` was added the same way in Phase 4, for backtest run
outputs.

Phase 4 also adds:
- `core/portfolio/portfolio.py` — Portfolio/PnL tracking. Lives in
  `core/`, not `research/`, deliberately — it's pure state logic with
  no file I/O and no dependency on this module, so it stays safe to
  import from anywhere (including a future live/paper-trading use, not
  just backtesting).
- `research/backtest/results.py` — persists a *completed* Portfolio's
  results using `save_dataset()` below. This is where the actual call
  into `research/storage.py` happens, since `core/portfolio/` itself
  is never allowed to import from `research/` (see the boundary rule
  above) — `core/portfolio/portfolio.py` explains this split in more
  detail if you're wiring the two together.

## Dataset storage — `research/storage.py`

Every dataset is versioned, never overwritten. Saving always creates
a new version; nothing is ever silently replaced. Each dataset also
has a `category` — `"raw"` for unmodified source data (Hansika's
historical downloads), `"processed"` for derived data (Gauri's
computed features), or `"results"` for completed backtest run outputs
(Phase 4) — matching the existing `data/raw`/`data/processed`/
`data/results` split.

```python
from research.storage import save_dataset, load_dataset, list_versions

# Saving raw historical data (Hansika)
version = save_dataset(
    "btcusdt_candles_1m",
    df,
    category="raw",
    source="hansika/historical_downloader",
    metadata={"start": "2024-01-01T00:00:00Z", "end": "2024-06-01T00:00:00Z", "gaps": []},
)

# Saving computed features (Gauri)
save_dataset(
    "btcusdt_returns_1m",
    features_df,
    category="processed",
    source="gauri/feature_engine",
    metadata={"computed_from": "btcusdt_candles_1m v3"},
)

# Saving backtest results (Phase 4) — usually via
# research/backtest/results.py's save_backtest_run() instead of calling
# save_dataset() directly, see that file for the full helper
save_dataset(
    "my_run_summary",
    summary_df,
    category="results",
    source="core.portfolio",
    metadata={"run_name": "my_run", "strategy_name": "stub_strategy"},
)

# Loading (defaults to the latest version)
df = load_dataset("raw", "btcusdt_candles_1m")
df_v1_specifically = load_dataset("raw", "btcusdt_candles_1m", version=1)

# Checking what's available
list_versions("raw", "btcusdt_candles_1m")
```

Each version is stored as
`data/<category>/<name>/v<N>/data.parquet` plus a `manifest.json`
recording row count, columns, a content checksum, who/what produced
it, and any freeform metadata (exact coverage, known gaps, etc.).

### Why this matters for the look-ahead-bias audit

Samarth's Phase 3 review specifically checks whether any feature uses
data that wouldn't have been available at the timestamp it's computed
for. Being able to point at an exact, immutable dataset version — not
"whatever the file currently contains" — is what makes that audit
possible to do with confidence. The `"computed_from"` metadata
convention above (recording exactly which raw dataset version a
processed dataset was derived from) is worth using consistently for
this reason.

## Where the actual data lives

`data/raw/`, `data/processed/`, and `data/results/` are gitignored —
dataset files (especially historical tick data and full backtest
trade logs) can get large, and don't belong in git history.
`research/storage.py` and this README are what's tracked; the data
itself is generated locally by running the downloaders/feature
pipelines/backtests.

## notebooks/ vs experiments/

- **`notebooks/`** — proper exploratory analysis, meant to be
  revisited and built on
- **`experiments/`** — genuinely scratch work; fine if it never gets
  cleaned up or goes anywhere

Neither folder is required to have "clean" code — that's the point of
keeping this separate from `core/`/`services/`.