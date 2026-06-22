# AGENTS.md — Rules for AI coding agents working in this repo

This project is designed to be extended by AI coding agents (Claude Code, Cursor, Codex,
etc.). These rules are **non-negotiable**. They protect the integrity of the research and
the safety of anyone who runs it.

## The 10 rules
1. **Do not invent trading performance.** Never fabricate metrics, returns, or win rates.
2. **Do not claim profitability without backtest evidence.** Cite a `backtest_run` id.
3. **Do not bypass risk controls.** All entries go through `risk.assess_trade`.
4. **Do not add live trading** unless the user explicitly requests it later, and even then
   only behind the disabled adapter boundary with its own review.
5. **Do not hide mock mode.** Mock forecasts must stay clearly labeled end-to-end
   (`mode="mock"`, `model_name="mock-gbm-v1"`, UI badge).
6. **Do not hardcode secrets.** Secrets come from env only; never commit `.env`.
7. **Do not use future candles in backtests.** Respect the no-lookahead contract.
8. **Do not treat Kronos output as a direct trade signal.** It is a probabilistic forecast;
   regime, structure and risk must gate it.
9. **Every strategy decision must have a reason code.** No bare buy/sell.
10. **Every metric must include costs** unless clearly marked gross.

## Working agreements
- Keep model integration inside `app/kronos/` and exchange integration inside
  `app/data/providers/`. Strategy code must not import `ccxt`, `torch`, or the model.
- Put thresholds/formulas in `configs/*.json`, not in code. Bump `*_version` when changing a
  formula.
- Add or update tests for any logic change (`backend/tests/`). Tests must be deterministic.
- Prefer typed interfaces (pydantic / Zod / TypeScript) over loose dicts at boundaries.
- When unsure whether something is real or mock output, check `mode` and surface it.

## Definition of a good PR here
Green tests, no new secrets, reason codes intact, costs included, mock honesty preserved,
docs updated, and a one-line note in `CHANGELOG.md`.
