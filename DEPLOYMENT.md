# DEPLOYMENT.md

## Option A — Docker Compose (recommended)
```bash
cp .env.example .env
docker compose up --build          # db + backend + frontend
# then, in another shell:
docker compose exec -T backend python /app/scripts/seed_database.py --ingest
```
- Dashboard: http://localhost:3000
- API + docs: http://localhost:8000 , http://localhost:8000/docs

`scripts/setup_local.sh` does build + up + wait-for-health + seed in one go.

## Option B — Local processes (no Docker for app)
Requires Python 3.11+, Node 20+, and a local PostgreSQL.
```bash
# Postgres (example via docker just for the DB)
docker run -d --name kat-db -e POSTGRES_USER=kronos -e POSTGRES_PASSWORD=kronos \
  -e POSTGRES_DB=kronos_terminal -p 5432:5432 postgres:16-alpine

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export KAT_DATABASE_URL=postgresql+psycopg2://kronos:kronos@localhost:5432/kronos_terminal
python ../scripts/seed_database.py --ingest
uvicorn app.main:app --reload --port 8000

# Frontend
cd ../frontend
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

## Enabling the REAL Kronos model
Mock mode runs with zero model files. To use the real model:
```bash
git clone https://github.com/shiyu-coder/Kronos vendor/Kronos
pip install -r backend/requirements-kronos.txt     # torch, transformers, ...
pip install -r vendor/Kronos/requirements.txt
# choose a variant in configs/kronos.default.json (small is the default), then:
#   set "mock_mode": "auto"  (use real if it loads) or "false" (require real)
```
Weights download from Hugging Face to `models/kronos_cache/` on first use. CPU works for
`Kronos-small`; a GPU is faster for `base`. Set `device` in the config (`auto`/`cuda:0`/
`cpu`/`mps`).

## Configuration
All tunables are JSON in `configs/` and editable from the Settings page (validated, written
to disk, reloaded live). Environment/secrets use the `KAT_` prefix (see `.env.example`).

## Migrations
`init_db()` auto-creates tables on startup for local/dev. For schema evolution use Alembic
(`cd backend && alembic revision --autogenerate -m "..."; alembic upgrade head`).

## Health & ops
- `GET /health` reports DB status, effective Kronos mode, scheduler, and the live-trading
  flag. The backend container has a Docker healthcheck on it.
- Scheduler runs are recorded in `scheduler_runs`; disable with `KAT_ENABLE_SCHEDULER=false`.
