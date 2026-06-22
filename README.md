# Kronos Alpha Terminal

A **local-first, AI-assisted trading research terminal** that uses
[Kronos](https://github.com/shiyu-coder/Kronos) — a foundation model for financial K-line
data — as a **probabilistic forecast engine** for crypto and stocks.

It does **not** spit out buy/sell calls. It produces forecast *distributions*, classifies
market regimes, scores reason-coded trade candidates, sizes them with a conservative risk
engine, and proves (or disproves) edge with walk-forward backtesting after fees and
slippage. It starts in **paper / research mode only**; live execution is isolated behind a
disabled, unshipped adapter.

> **Kronos chooses the battlefield. Market structure chooses the entry. The risk model
> chooses the size. Backtesting decides whether the edge is real.**

---

## What this project does
- Ingests OHLCV candles (Binance public via CCXT by default; yfinance optional).
- Forecasts the next N candles as a **distribution** (median + q10/q25/q75/q90, p_up/p_down).
- Runs in **mock mode** with zero model files, clearly labeled, so it always works.
- Detects market **regime** with a human-readable explanation.
- Scores **reason-coded** trade candidates with a versioned, config-driven edge formula.
- Confirms entries via **market structure** and rejects late entries.
- Sizes positions and enforces **risk limits + a kill switch**.
- Backtests **walk-forward** (no lookahead) vs baselines, net of costs.
- Simulates **paper trades** through the same risk engine.
- Ships a **dashboard**, a **REST API**, tests, and full docs.

## What it does NOT do
- ❌ No live trading (no shipped adapter; flag defaults off).
- ❌ No financial advice, no profit guarantee, no signal-selling.
- ❌ No HFT (default timeframe 1h).
- ❌ Never presents **mock** output as real, or **gross** returns as net.

---

## Quick start (Docker)
```bash
cd kronos_alpha_terminal
cp .env.example .env
docker compose up --build           # db + backend + frontend
# in another shell, once backend is healthy:
docker compose exec -T backend python /app/scripts/seed_database.py --ingest
```
- Dashboard → http://localhost:3000
- API + docs → http://localhost:8000 / http://localhost:8000/docs

Or one shot: `bash scripts/setup_local.sh`. Common tasks via `make` (see `make help`).

## Project layout
```
backend/    FastAPI app (data, kronos adapter, strategy, risk, backtesting, paper, api)
frontend/   Next.js dashboard (TanStack Query, Recharts, Zod)
configs/    versioned JSON tunables (risk, strategy, kronos, backtest, assets, timeframes)
scripts/    seed / forecast / backtest / export CLIs
mcp/ skills/ prompts/   AI-agent integration + behavior docs
docs/ notebooks/         diagrams, examples, research notebooks
```

## Environment variables
Defined in `.env` (see `.env.example`). No third-party keys needed for the default setup.

| Var | Default | Meaning |
|-----|---------|---------|
| `KAT_DATABASE_URL` | postgres on localhost:5432 | Backend DB connection |
| `KAT_MOCK_MODE` | `auto` | `auto` / `true` (force mock) / `false` (require real) |
| `KAT_ENABLE_LIVE_TRADING` | `false` | Stays off; no live adapter ships |
| `KAT_ENABLE_SCHEDULER` | `true` | Background ingest/signal/paper jobs |
| `KAT_CORS_ORIGINS` | http://localhost:3000 | Allowed dashboard origin |
| `NEXT_PUBLIC_API_BASE` | http://localhost:8000 | Frontend → API base URL |

## How to ingest data
- UI: **Assets** page → "Ingest 1h".
- CLI: `make ingest_crypto` (or `python scripts/seed_database.py --ingest`).
- API: `POST /ingest/candles {"symbol":"BTC/USDT","timeframe":"1h","lookback_candles":1500}`.

## How to run a forecast
- UI: **Forecasts** page → pick symbol → "Run forecast (24h)".
- API: `POST /forecasts/run {"symbol":"BTC/USDT","timeframe":"1h"}` then `GET /forecasts/{id}`.
- The fan chart shows the q10–q90 band and median; a **MOCK** badge appears in mock mode.

## How to run signals
- UI: **Dashboard / Signals** → "Run signals".
- CLI: `make signals`. API: `POST /signals/run`, read with `GET /signals/latest`.

## How to run a backtest
- UI: **Backtests** → "Run backtest".
- CLI: `make backtest`. API: `POST /backtests/run`, read with `GET /backtests/{id}`.
- Output includes metrics (net of costs), the equity curve, and the baseline comparison
  with a **beats baselines** verdict.

## How to use paper trading
- UI: **Paper** page → choose symbol/side → "Open paper order" (risk engine sizes + gates
  it) → close manually or let the scheduler hit stop/TP.
- API: `POST /paper/orders`, `POST /paper/orders/{id}/close`, `GET /paper/orders`.
- Reset the book with `make paper_reset`.

## How to interpret output
- **Forecast**: `p_up` is the share of paths ending higher; the band is uncertainty, not a
  promise. `forecast_volatility_ratio` > 1 means more turbulence than recent history.
- **Signal status**: `long/short_candidate` (actionable), `watch` (forming), `no_edge`, or a
  `blocked_by_*` reason. Always read the `reason_codes`.
- **Edge score**: combines direction, asymmetry, path quality and regime, minus a volatility
  penalty (see [SIGNAL_SPEC.md](SIGNAL_SPEC.md)).
- **Backtest**: judge on Sharpe / profit factor / max drawdown **after costs**, vs baselines.
- **Mock vs real**: check the `mode` badge on every chart. Mock is for plumbing, not edge.

## Common failure modes
- **"Not enough candle history"** → ingest more candles first (`make ingest_crypto`).
- **Everything is `blocked_by_*` / `no_edge`** → expected with conservative defaults and/or
  mock forecasts; loosen thresholds in **Settings** for experimentation.
- **`MockModeForbiddenError`** → you set `mock_mode=false` but the real model can't load;
  install `requirements-kronos.txt` + clone Kronos, or switch to `auto`.
- **DB connection errors** → ensure Postgres is up (`docker compose up db`) and
  `KAT_DATABASE_URL` is correct.
- **yfinance/stock issues** → stocks are disabled by default and rate-limited; enable per
  asset only after verifying data.

## Enabling the real Kronos model
```bash
git clone https://github.com/shiyu-coder/Kronos vendor/Kronos
pip install -r backend/requirements-kronos.txt
pip install -r vendor/Kronos/requirements.txt
# set "mock_mode": "auto" (or "false") in configs/kronos.default.json
```
Weights download to `models/kronos_cache/`. `Kronos-small` runs on CPU; use a GPU for
`base`. See [DEPLOYMENT.md](DEPLOYMENT.md).

## Tests
```bash
cd backend && python -m pytest -q     # 40 tests: data contract, mock adapter,
                                      # signal scoring, risk engine, no-leakage
```

## Documentation
[PRD](PRD.md) · [ARCHITECTURE](ARCHITECTURE.md) · [DATA_CONTRACT](DATA_CONTRACT.md) ·
[SIGNAL_SPEC](SIGNAL_SPEC.md) · [BACKTEST_SPEC](BACKTEST_SPEC.md) ·
[RISK_ENGINE](RISK_ENGINE.md) · [SECURITY](SECURITY.md) · [DEPLOYMENT](DEPLOYMENT.md) ·
[MCP](MCP.md) · [AGENTS](AGENTS.md) · [CHANGELOG](CHANGELOG.md)

## Legal & risk note
This software is a **research and educational tool**. It is **not financial advice**, not an
investment product, and provides **no guarantee of profit**. Markets are risky; forecasts
are probabilistic and may be mock output. You are solely responsible for any decisions you
make. The upstream Kronos model is licensed separately — review and comply with its license.
Licensed under [MIT](LICENSE).

## Roadmap
- Real-model batch forecasting + forecast caching in backtests.
- Portfolio-level backtester (cross-symbol limits in-sim).
- Candlestick chart + richer regime visualizations.
- More providers (perps/funding), more timeframes, multi-timeframe forecasts.
- Calibration monitoring (see `notebooks/calibration.ipynb`) and drift alerts.
- Optional, reviewed live-execution adapter (still off by default).
