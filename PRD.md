# PRD — Kronos Alpha Terminal

## 1. Product name
**Kronos Alpha Terminal** — a local-first, AI-assisted trading research terminal.

## 2. Problem statement
Serious solo traders drown in noise. Most "AI trading" tools either (a) output naive
buy/sell calls with no probability, no risk, and no proof of edge, or (b) are black-box
SaaS that you cannot audit, run locally, or trust with capital. There is no honest,
inspectable tool that turns a probabilistic market forecast into *disciplined trade
candidates* — with regime context, structural entries, risk limits, and walk-forward
proof — while refusing to pretend it is certain.

Kronos Alpha Terminal fixes this. It uses **Kronos** (a foundation model for financial
K-line data) as a probabilistic forecast engine, then layers regime detection, signal
scoring, market-structure confirmation, risk sizing and walk-forward backtesting on top.
It starts in **paper/research mode only**. Live execution is isolated behind a disabled
adapter.

Core principle:

> **Kronos chooses the battlefield. Market structure chooses the entry. The risk model
> chooses the size. Backtesting decides whether the edge is real.**

## 3. Target user
A serious solo trader / quant researcher who:
- can run Docker and read JSON config,
- wants probabilistic forecasts, not tips,
- demands risk limits and proof of edge before risking money,
- wants everything local and auditable.

## 4. Non goals
- **Not** an auto-trader. No live order routing ships enabled.
- **Not** financial advice or a signal-selling service.
- **Not** an HFT / sub-second system. Default timeframe is 1h.
- **Not** a portfolio optimizer or tax tool.
- **Not** a guarantee of profit. The system can and will say "no edge".

## 5. Core workflows
1. **Ingest** historical candles for a small universe (BTC/ETH/SOL, 1h).
2. **Forecast** the next 24 candles as a distribution (median + q10/q90 + p_up).
3. **Classify** the market regime (trend/range/volatility/panic) with an explanation.
4. **Score** each asset into a reason-coded trade candidate (or a block/watch/no-edge).
5. **Confirm** entries via market structure; size via the risk engine.
6. **Backtest** the whole pipeline walk-forward, after fees and slippage, vs baselines.
7. **Paper trade** candidates through a risk-checked simulated ledger.
8. **Export** results; **tune** config without editing source.

## 6. Functional requirements
- FR1 Ingest OHLCV via CCXT (crypto) / yfinance (stocks, optional) into Postgres.
- FR2 Validate candles against the data contract; detect and flag gaps.
- FR3 Produce a forecast **distribution** (not a point estimate) via the Kronos adapter.
- FR4 Fall back to clearly-labeled **mock** mode if the real model can't load; never
  silently downgrade when real output is demanded.
- FR5 Detect market regime with a human-readable explanation.
- FR6 Score signals with a versioned, config-driven edge formula and reason codes.
- FR7 Require market-structure confirmation and reject late entries.
- FR8 Size positions from risk, enforce exposure/correlation/daily-loss limits, kill switch.
- FR9 Walk-forward backtest with no lookahead, fees, slippage, and baseline comparison.
- FR10 Paper ledger: open/close simulated orders through the risk engine.
- FR11 REST API + dashboard for every workflow.
- FR12 Edit all thresholds via config (JSON) or the Settings page — no code edits.

## 7. Non functional requirements
- NFR1 Runs locally with one Docker command; no paid API required for default use.
- NFR2 Deterministic tests; mock forecasts reproducible from a seed.
- NFR3 Typed interfaces (pydantic / TypeScript / Zod); structured logging.
- NFR4 Isolated model and exchange integration (adapters).
- NFR5 No secrets in source or config files.
- NFR6 The app must not crash if model files are unavailable.

## 8. Risk requirements
See [RISK_ENGINE.md](RISK_ENGINE.md). Defaults: 0.5% risk/trade, 1.5% max daily loss,
max 2 open positions, max 1 correlated position, **no leverage**, **no live trading**,
mandatory stop on every trade, kill switch on consecutive losses / data errors / model
uncertainty / wide spreads.

## 9. Data requirements
See [DATA_CONTRACT.md](DATA_CONTRACT.md). Canonical UTC OHLCV schema, uniqueness on
(symbol, exchange, timeframe, timestamp_open), OHLC validity checks, gap detection,
raw vs processed separation.

## 10. Backtesting requirements
See [BACKTEST_SPEC.md](BACKTEST_SPEC.md). Walk-forward only; no future candles; fees +
slippage mandatory; baselines (buy&hold, EMA trend, ATR breakout, random) required; a
strategy is "valid" only if it beats baselines on risk-adjusted metrics after costs.

## 11. Paper trading requirements
No real orders. Ledger stores order id, symbol, side, entry/exit, stop, take-profit,
size, risk amount, thesis, forecast id, signal id, status, realized pnl, fees, slippage,
exit reason. Every paper order is sized and gated by the same risk engine as a live order
would be.

## 12. UI requirements
Dashboard (regime, top long/short candidates, volatility expansion, blocked setups, risk,
scheduler), Forecast (candles + fan chart + diagnostics + mock warning), Signals (ranked,
reason-coded), Backtests (config, equity/drawdown, metrics, baselines, export), Paper
(open/closed, equity, risk usage, manual order), Settings (all config editable).

## 13. Acceptance criteria
The project is **done** only when a user can:
1. Start the full stack locally with one command.
2. Select BTC/USDT and ETH/USDT.
3. Ingest historical 1h candles.
4. Run a Kronos forecast for the next 24 candles.
5. See the forecast distribution on a chart.
6. See ranked assets by edge score.
7. See the market regime label.
8. Run a walk-forward backtest.
9. View performance metrics after fees and slippage.
10. Simulate paper trades.
11. Export results as CSV.
12. Change config without editing source code.
13. Run tests.

## 14. Milestones
- **M1 Skeleton** — repo, docs, Docker, DB schema, config loader. ✅
- **M2 Data** — ingestion, validation, gap detection, assets page. ✅
- **M3 Forecast** — Kronos adapter, mock + real, forecast chart. ✅
- **M4 Signals** — scoring, regime, ranking, reason codes. ✅
- **M5 Backtest** — walk-forward, fees/slippage, baselines, metrics. ✅
- **M6 Paper + Risk** — ledger, risk engine, dashboard. ✅
- **M7 Polish** — tests, docs, export, local setup. ✅

## 15. Definition of done
All acceptance criteria pass; backend tests green; mock mode works with zero model files;
no live-trading path is reachable; every signal carries a reason code; every reported
return is net of costs unless explicitly labeled gross; no secrets in git.
