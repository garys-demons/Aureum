# Project Compass

Event-driven quant research & trading platform. See `docs/` for the full
architecture and phase roadmap.

## Phase 1 — Data Spine (Day 1 setup)

```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

This will:
1. Create a virtualenv and install dependencies (`pydantic`, `pytest`, `websockets`, `asyncpg`, `structlog`, etc.)
2. Start Postgres/TimescaleDB via Docker Compose (`infra/docker/docker-compose.yml`)

Then:
```bash
cp .env.example .env   # fill in DB url / API keys as needed
pytest                  # confirm scaffolding works
```

## Repository structure

```
project-compass/
  apps/           api, dashboard
  services/       market_data, news, ai_reasoning, trading
  core/           events, models, strategy, risk, execution, portfolio
  research/       notebooks, experiments
  data/           raw, processed
  config/         exchange.yaml, risk.yaml, strategy.yaml
  tests/          unit, integration, replay
  scripts/
  infra/          docker
  docs/
```

Note: `core/risk` deliberately has no import path to `core/strategy` or
`services/ai_reasoning` — the risk engine must be checkable/testable in
total isolation, since it's the one component allowed to override
everything above it. Keep it that way as the codebase grows.

## Status

- [x] Exchange confirmed: Binance Spot Testnet
- [x] Repo skeleton
- [x] Docker Compose (Postgres/TimescaleDB)
- [x] Virtualenv + pydantic/pytest scaffolding
- [x] `ExchangeAdapter` interface stub
- [ ] `BinanceAdapter.stream_market_data` (Day 3 — Hansika)
- [ ] `BinanceAdapter.fetch_historical_candles` (Day 4 — Gauri)

## Database

Default: shared Timescale Cloud instance for the team (ask Samarth for the connection string).
Set it in your `.env` as `DATABASE_URL`.

Alternative: run Postgres locally via Docker —
`docker compose -f infra/docker/docker-compose.yml up -d`
