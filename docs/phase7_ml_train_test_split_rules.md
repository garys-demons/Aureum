# Phase 7 - ML Train/Test Split Discipline

**Owner:** Hansika
**Extends:** Phase 3 look-ahead-bias audit, applied specifically to ML model training

---

## The Rule (Non-Negotiable)

**Any model trained in this project must use a chronological train/test split. Never random, never shuffled.**

Standard ML practice often splits data randomly (e.g. sklearn's default train_test_split) because for most datasets, row order doesn't matter - a photo of a cat is a photo of a cat regardless of when it was taken. Financial time-series data is different: order is information. A model that trains on tomorrow's price movement and is tested on today's has effectively been shown the answer before the exam.

---

## Why This Matters - Concretely

If a model is trained on a random 80% of rows and tested on the remaining 20%, it is entirely possible (likely, even) that some training rows have timestamps later than some test rows. The model never explicitly "sees the future" in any single row, but it learns patterns from a dataset that, taken as a whole, includes information from after the point it's being evaluated against. This makes the evaluation results look better than the model's real, deployable performance - a classic silent failure mode, since nothing about it looks obviously wrong without checking.

---

## The Correct Approach

1. Sort/select by timestamp, never by row position or random seed.
2. Pick a single split timestamp. Everything strictly before it is training data. Everything at or after it is test data.
3. Consider an embargo gap when features are computed over rolling windows (e.g. Phase 3's rolling_volatility, rsi). A test-row's feature value can be influenced by training-set rows just before the cutoff, even if the row's own timestamp is technically past it. An embargo (a dropped buffer zone around the cutoff) removes this subtler leak.
4. Audit every split before trusting it - use research.ml_split.audit_split_for_leakage() to programmatically confirm no training timestamp is >= the earliest test timestamp.

---

## Implementation

research/ml_split.py:
- chronological_split(items, timestamp_fn, split_timestamp, embargo_seconds=0)
- audit_split_for_leakage(result, timestamp_fn)

6 unit tests cover: correct separation, order-independence (input row order never matters, only timestamps), embargo behavior, and explicit leakage detection on a deliberately-broken split.

---

## Scope

This applies to any model training that happens from Phase 7 onward. As of this document, no model has been trained yet in this project - this is the rulebook other team members (starting with Samarth's Phase 7 reasoning component, if it trains anything) must follow.

---

## Bug Fixed: recent_24h Reproducibility Issue (Phase 6 to Phase 7)

**Issue:** research/download_sensitivity_windows.py computed window boundaries relative to time.time() at download time. The same window name (recent_24h) therefore referred to a genuinely different dataset on every run - a benchmark that changes underneath you is not a benchmark.

**Proof of the bug (before fix):** two runs of a simple timestamp calculation, 9 seconds apart, produced different results. Run 1 produced 1787993393566. Run 2 produced 1787993402815.

**Fix:** windows are now computed from a single, pinned FIXED_REFERENCE_MS constant (2026-08-27T00:00:00Z, verified via datetime.datetime(2026, 8, 27, 0, 0, 0, tzinfo=timezone.utc)), never recomputed from time.time().

**Proof of the fix (after fix):** two full downloader runs, 8 seconds apart, produced identical window boundaries and identical data checksums. Version 1 produced start_time_ms=1787702400000, end_time_ms=1787788859999, checksum=cc297f25e02d3ba5. Version 2 produced the exact same values: start_time_ms=1787702400000, end_time_ms=1787788859999, checksum=cc297f25e02d3ba5. Only version and created_at differ between the two runs, exactly as expected - the underlying data and its boundaries are now genuinely fixed.

**Why this matters for Phase 7/8:** AI evaluation results are only meaningful if compared against a stable benchmark. A silently-shifting recent_24h would have made any "AI vs baseline" comparison impossible to reproduce or trust.