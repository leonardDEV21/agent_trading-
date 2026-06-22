# Kronos Alpha Terminal — developer commands.
# Most data tasks run inside the backend container (no local Python deps needed).
# `make setup` then `make dev` is the one-command-ish path; see README.

COMPOSE := docker compose

.PHONY: help setup dev down logs backend frontend test ingest_crypto forecast signals backtest paper_reset seed clean

help:
	@echo "Targets: setup dev down logs backend frontend test ingest_crypto forecast signals backtest paper_reset seed clean"

setup:                       ## copy .env and build images
	@test -f .env || cp .env.example .env
	$(COMPOSE) build

dev:                         ## start the full stack (db + backend + frontend)
	$(COMPOSE) up

down:                        ## stop the stack
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

seed:                        ## create tables, register assets, ingest default candles
	$(COMPOSE) exec -T backend python /app/scripts/seed_database.py --ingest

ingest_crypto:               ## ingest 1h candles for the default crypto universe
	$(COMPOSE) exec -T backend python /app/scripts/seed_database.py --ingest

forecast:                    ## run a forecast for every enabled asset
	$(COMPOSE) exec -T backend python /app/scripts/run_forecast_batch.py

signals:                     ## run forecast + regime + signal scoring for all assets
	$(COMPOSE) exec -T backend python /app/scripts/run_forecast_batch.py --signals

backtest:                    ## run the default walk-forward backtest
	$(COMPOSE) exec -T backend python /app/scripts/run_backtest.py

export:                      ## export latest signals + backtest to data/exports
	$(COMPOSE) exec -T backend python /app/scripts/export_results.py

paper_reset:                 ## wipe the paper trading book
	$(COMPOSE) exec -T backend python /app/scripts/seed_database.py --reset-paper

backend:                     ## run backend locally (needs local deps + postgres)
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:                    ## run frontend locally (needs npm install)
	cd frontend && npm run dev

test:                        ## run backend tests locally
	cd backend && python -m pytest -q

test-docker:                 ## run backend tests inside the container
	$(COMPOSE) exec -T backend python -m pytest -q

clean:
	$(COMPOSE) down -v
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
