# ARCHITECTURE.md

```
                ┌─────────────────────────────────────────────────────────┐
                │                    Next.js dashboard                      │
                │  dashboard · forecasts · signals · backtests · paper ·    │
                │  assets · settings   (TanStack Query + Recharts + Zod)    │
                └───────────────────────────┬─────────────────────────────┘
                                            │ REST (JSON)
                ┌───────────────────────────▼─────────────────────────────┐
                │                     FastAPI backend                       │
                │  routes → scheduler.jobs (orchestration) → engines        │
                │                                                           │
                │  data(providers/ingestion)  kronos(adapter)  strategy     │
                │  risk  backtesting  paper   repositories                  │
                └───────────────┬───────────────────────────┬─────────────┘
                                │                            │
                        ┌───────▼────────┐          ┌────────▼────────┐
                        │   PostgreSQL    │          │  Kronos model    │
                        │  (17 tables)    │          │  (real or MOCK)  │
                        └─────────────────┘          └─────────────────┘
```

## 1. Frontend architecture
Next.js 14 (app router), TypeScript, Tailwind. Server components for the shell; client
components for interactive pages. `TanStack Query` owns server state and caching; `Zod`
validates payloads at the edge; `Recharts` renders the forecast fan, equity curve and
price charts. A single typed API client (`lib/api.ts`) centralizes the base URL and error
handling. Mock-mode and "no live trading" are surfaced as persistent badges.

## 2. Backend architecture
FastAPI app (`app/main.py`) wires routers, CORS, a typed exception handler and an optional
APScheduler. Each domain is an isolated package:
- `data/` — providers (CCXT/yfinance) + ingestion/validation/gap detection.
- `kronos/` — the forecast adapter (the ONLY entry point to the model).
- `strategy/` — regime, market structure, signal scoring, ranking, confirmation.
- `risk/` — sizing, stops, take-profit, exposure limits, kill switch.
- `backtesting/` — walk-forward, simulator, fees, slippage, metrics, baselines.
- `paper/` — order simulator, portfolio, ledger.
- `repositories/` — all DB access.
- `scheduler/jobs.py` — orchestration reused by routes, cron and CLI scripts.

## 3. Database schema
PostgreSQL via SQLAlchemy 2.0. Tables: `assets, candles, data_gaps, forecast_runs,
forecast_paths, signals, signal_explanations, regime_snapshots, backtest_runs,
backtest_trades, backtest_equity, paper_orders, paper_positions, risk_events,
scheduler_runs, configs, audit_logs`. Timestamps are tz-aware UTC; money/price columns use
`Numeric`; reason codes and forecast paths are JSON. The engine is created **lazily** so
importing models never requires a live DB driver.

## 4. Data flow
`provider.fetch_candles → validate → upsert (dedupe) → gap-detect → candles table`.
Read path returns a UTC-indexed OHLCV(+amount) DataFrame for the forecast/backtest engines.

## 5. Forecast pipeline
`candles_to_df → KronosAdapter.prepare_context (last N candles + future timestamps) →
predict (real: loop upstream predict(sample_count=1) to collect S paths; mock: seeded GBM)
→ postprocess (quantile paths, p_up/p_down, return quantiles, forecast vol ratio,
uncertainty) → ForecastDistribution`. Upstream `predict` averages its internal samples, so
we collect **independent paths** to build a true distribution. Output is persisted to
`forecast_runs` + `forecast_paths`, always tagged with `mode` (real/mock) and a
`model_config_hash`.

## 6. Signal pipeline
`forecast + regime + market structure + costs → edge formula v1 → trade_candidate_status
+ reason codes`. See [SIGNAL_SPEC.md](SIGNAL_SPEC.md). Optionally demoted by a
higher-timeframe confirmation layer. Persisted to `signals` + `signal_explanations`.

## 7. Backtest pipeline
Walk-forward folds per symbol; at each decision point only past candles are visible;
entry executes at the next candle open; stop/tp/max-hold/regime-flip exits with fees and
slippage; equity threaded across folds; baselines run over the same range. See
[BACKTEST_SPEC.md](BACKTEST_SPEC.md). Persisted to `backtest_runs/_trades/_equity`.

## 8. Scheduler
APScheduler (disabled unless `KAT_ENABLE_SCHEDULER=true`). Hourly: ingest → signals.
Every 5 min: manage open paper orders (stop/tp checks). Each run is recorded in
`scheduler_runs`; a job failure never kills the scheduler thread.

## 9. Error handling
Typed exception hierarchy (`app/core/errors.py`) mapped to HTTP codes by a FastAPI handler
returning `{code, message, detail}`. Notable: `DataProviderError` (502, trips kill switch),
`ModelLoadError` (503), `MockModeForbiddenError` (503, when real output demanded but
unavailable), `RiskBlockedError` (409).

## 10. Logging
`structlog`: human-readable locally, JSON when `KAT_LOG_JSON=true`. Context (symbol,
forecast id, reason codes) travels with log lines.

## 11. Security boundaries
- Live trading gated by `KAT_ENABLE_LIVE_TRADING` (default false) **and** there is no
  shipped live adapter. The paper ledger ignores the flag by design.
- Secrets only via environment (`.env`, gitignored). Never in config JSON or code.
- Exchange + model integration isolated behind adapters.
See [SECURITY.md](SECURITY.md).

## 12. Model cache handling
Real Kronos weights download to `models/kronos_cache/` (mounted volume). The upstream repo
is cloned to `vendor/Kronos` and added to `sys.path` lazily. If torch, the vendor repo, or
the weights are missing, the adapter raises a clean error and (in `auto` mode) falls back
to labeled mock — the app never crashes for a missing model.

## 13. Deployment options
Local Docker Compose (default), or run backend + frontend processes directly against a
local Postgres. See [DEPLOYMENT.md](DEPLOYMENT.md).
