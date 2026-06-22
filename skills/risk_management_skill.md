# Skill: Risk management

See [RISK_ENGINE.md](../RISK_ENGINE.md). Engine: `app/risk/`. Every entry passes through
`risk.assess_trade`.

## No position without a stop
- Stops are mandatory and computed by `stop_engine.py` (ATR or structural invalidation,
  whichever is safer), never tighter than `min_stop_distance_pct`.

## No leverage by default
- `allow_leverage=false`; notional capped at account size (reduces risk below target).

## Daily loss limits
- `max_daily_loss` (default 1.5%) halts new entries and trips the kill switch.

## Correlation limits
- `max_correlated_positions` per `beta_group` (e.g. `btc_beta`). Don't stack correlated risk.

## Kill switch
- Trips on consecutive losses, data-provider errors, model uncertainty, or wide spreads.
- State persists in `risk_events`; auto-clears after `cooldown_minutes`.

## Position sizing
- Size from dollar risk: `size = account * risk_per_trade / |entry - stop|`.
- Reject orders below the asset's min notional.

## When extending
- Add new limits inside `assess_trade` with a dedicated `ReasonCode`; add a unit test.
- Never add a code path that opens a position bypassing `assess_trade`.
