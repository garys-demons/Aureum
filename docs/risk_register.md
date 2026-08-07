# Aureum — Risk Register

Running log of risks, gaps, and issues found during review. Owned by Review & Risk (Samarth).

**Severity:** Low = worth knowing · Medium = should fix soon · High = fix before proceeding

| Date | Found in | Issue | Severity | Status |
|------|----------|-------|----------|--------|
| 2026-08-06 | Aryan PR #2 | `aiosqlite` used in tests but not declared in `pyproject.toml` — tests fail on clean install | Medium | Fixed |
| 2026-08-06 | Aryan PR #2 | `SENSITIVE_KEYS` is a fixed exact-match set — a secret logged under an unlisted key name won't be redacted | Low | Open |
| 2026-08-06 | `scripts/setup.sh` | Uses `python` (Windows-specific); breaks on Mac/Linux where `python3` is standard | Low | Open |
| 2026-08-07 | Live connect test | `received_time` ~1600ms earlier than `event_time` — local clock skew vs Binance. Breaks PRD p95 <200ms latency measurement and any staleness check | Medium | Open |
| 2026-08-07 | Security (forward-looking) | Testnet API keys not yet created — when added, must have withdrawal permissions disabled | Medium | Open |
| 2026-08-07 | Aryan PR #2 | `SENSITIVE_KEYS` redaction never tested against real secret values (only empty strings so far) | Low | Open |
| 2026-08-07 | Integration gap | `scripts/test_connect.py` prints to console only — unclear if market data stream is wired to Aryan's `repository.py` persistence. Phase 1 exit requires data landing in Postgres | High | Open |
| 2026-08-07 | DB connectivity | Timescale connection timed out (worked previously) — if free-tier auto-pause, sustained 1hr collection run may be interrupted | Medium | Investigating |
| 2026-08-07 | DB / Timescale | Free-tier instance auto-pauses when idle. Sustained 1hr collection run (Phase 1 exit) could be interrupted; must confirm pause policy and whether active writes prevent it | Medium | Open |
| 2026-08-07 | DB / persistence | Shared Timescale DB contains ZERO tables — models.py defines schemas but no migration has ever run against the real database. Persistence tests pass only because they use in-memory SQLite | High | Open |
