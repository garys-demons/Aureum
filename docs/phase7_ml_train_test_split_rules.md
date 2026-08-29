# Phase 7 — ML Train/Test Split Discipline

**Owner:** Hansika
**Extends:** Phase 3 look-ahead-bias audit, applied specifically to ML model training

---

## The Rule (Non-Negotiable)

**Any model trained in this project must use a chronological
train/test split. Never random, never shuffled.**

Standard ML practice often splits data randomly (e.g. `sklearn`'s
default `train_test_split`) because for most datasets, row order
doesn't matter — a photo of a cat is a photo of a cat regardless of
when it was taken. **Financial time-series data is different: order
is information.** A model that trains on tomorrow's price movement and
is tested on today's has effectively been shown the answer before the
exam.

---

## Why This Matters — Concretely

If a model is trained on a random 80% of rows and tested on the
remaining 20%, it is entirely possible (likely, even) that some
training rows have timestamps *later* than some test rows. The model
never explicitly "sees the future" in any single row, but it learns
patterns from a dataset that, taken as a whole, includes information
from after the point it's being evaluated against. This makes the
evaluation results look better than the model's real, deployable
performance — a classic silent failure mode, since nothing about it
looks obviously wrong without checking.

---

## The Correct Approach

1. **Sort/select by timestamp, never by row position or random seed.**
2. **Pick a single split timestamp.** Everything strictly before it is
   training data. Everything at or after it is test data.
3. **Consider an embargo gap** when features are computed over rolling
   windows (e.g. Phase 3's `rolling_volatility`, `rsi`). A test-row's
   feature value can be influenced by training-set rows just before
   the cutoff, even if the row's own timestamp is technically past it.
   An embargo (a dropped buffer zone around the cutoff) removes this
   subtler leak.
4. **Audit every split before trusting it** — use
   `research.ml_split.audit_split_for_leakage()` to programmatically
   confirm no training timestamp is >= the earliest test timestamp.

---

## Implementation

`research/ml_split.py`:
- `chronological_split(items, timestamp_fn, split_timestamp, embargo_seconds=0)`
- `audit_split_for_leakage(result, timestamp_fn)`

6 unit tests cover: correct separation, order-independence (input row
order never matters, only timestamps), embargo behavior, and explicit
leakage detection on a deliberately-broken split.

---

## Scope

This applies to any model training that happens from Phase 7 onward.
As of this document, no model has been trained yet in this project —
this is the rulebook other team members (starting with Samarth's
Phase 7 reasoning component, if it trains anything) must follow.