#!/usr/bin/env bash
# One-shot local setup: env, build, start, seed, ingest.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Creating .env from .env.example"
  cp .env.example .env
fi

echo "Building images…"
docker compose build

echo "Starting database…"
docker compose up -d db
sleep 3

echo "Starting backend + frontend…"
docker compose up -d backend frontend

echo "Waiting for backend health…"
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "Backend is up."
    break
  fi
  sleep 2
done

echo "Seeding database + ingesting candles…"
docker compose exec -T backend python /app/scripts/seed_database.py --ingest

cat <<'EOF'

Setup complete.
  Dashboard: http://localhost:3000
  API docs:  http://localhost:8000/docs

Next:
  make signals     # generate signals
  make backtest    # run walk-forward backtest
EOF
