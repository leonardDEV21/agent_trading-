# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] — initial
### Added
- Full repo scaffold: backend (FastAPI), frontend (Next.js), Postgres schema, Docker Compose.
- Kronos adapter with **mock** (seeded GBM) and **real** modes; honest mode labeling and
  `MockModeForbiddenError` when real output is demanded but unavailable.
- Forecast distribution (median + q10/q25/q75/q90 paths, p_up/p_down, return quantiles,
  forecast volatility ratio, uncertainty score).
- Data pipeline: CCXT/yfinance providers, ingestion, candle data-contract validation,
  duplicate prevention, gap detection.
- Strategy engines: regime detector (with explanations), market-structure entries,
  config-driven edge formula v1, ranking, higher-timeframe confirmation.
- Risk engine: risk-based sizing, ATR/structure stops, R:R take-profit, exposure +
  correlation limits, daily-loss limit, kill switch.
- Walk-forward backtester with no lookahead, fees, slippage, baselines, and full metrics.
- Paper ledger routed through the risk engine; portfolio + risk status.
- REST API for every workflow; APScheduler jobs; CLI scripts.
- 40 backend tests (data contract, mock adapter, signal scoring, risk engine, no-leakage).
- Documentation set: PRD, ARCHITECTURE, DATA_CONTRACT, SIGNAL_SPEC, BACKTEST_SPEC,
  RISK_ENGINE, SECURITY, DEPLOYMENT, MCP, AGENTS; MCP/skill/prompt templates.

### Notes
- Default forecast mode is `auto` (real if it loads, else labeled mock).
- Live trading is disabled and not shipped.
