\# Aureum — Risk Register



Running log of risks, gaps, and issues found during review. Owned by Review \& Risk (Samarth).



\*\*Severity:\*\* Low = worth knowing · Medium = should fix soon · High = fix before proceeding



| Date | Found in | Issue | Severity | Status |

|------|----------|-------|----------|--------|

| 2026-08-06 | Aryan PR #2 | `aiosqlite` used in tests but not declared in `pyproject.toml` — tests fail on any clean install | Medium | Fixed |

| 2026-08-06 | Aryan PR #2 | `SENSITIVE\_KEYS` in `logging\_config.py` is a fixed exact-match set — a secret logged under an unlisted key name won't be redacted | Low | Open |

| 2026-08-06 | `scripts/setup.sh` | Uses `python` (Windows-specific); would break on Mac/Linux where `python3` is standard | Low | Open |

