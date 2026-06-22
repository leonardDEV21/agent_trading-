# Skill: Code review

A checklist for reviewing changes in this repo. Block the PR if any item fails.

## Check security
- No secrets added (grep for keys/tokens). Secrets only via env.
- No new public network surface; CORS still scoped.
- No code path that enables live trading.

## Check tests
- `make test` is green. New logic has deterministic tests.
- No-leakage and risk tests still pass.

## Check leakage
- Backtest decisions use only past candles; entries fill at next open.
- No use of the current bar's close to decide the current entry.

## Check type safety
- Pydantic models / TypeScript / Zod at boundaries. No untyped dicts leaking across layers.

## Check config handling
- New thresholds live in `configs/*.json`, not hardcoded. `*_version` bumped if a formula
  changed. Settings update path still validates.

## Check failure states
- Missing model files → labeled mock (auto) or clean error (false), never a crash.
- Provider errors raise `DataProviderError`; risk decisions return reason codes.
- Mock honesty preserved end-to-end; metrics include costs.
