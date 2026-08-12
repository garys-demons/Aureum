#!/usr/bin/env bash
# Day 1 setup: venv + deps + spin up Postgres/TimescaleDB
set -e

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

echo ""
echo "Venv ready. Starting TimescaleDB via Docker Compose..."
docker compose -f infra/docker/docker-compose.yml up -d

echo ""
echo "Done. Run 'pytest' to confirm the scaffolding works."
