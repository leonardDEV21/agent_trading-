# RISK_ENGINE.md

Conservative by default. The risk engine is the single gate every new entry (paper or
backtest) passes through: [`app/risk/`](backend/app/risk/). Config:
[`configs/risk.default.json`](configs/risk.default.json).

## Defaults
| Rule | Default |
|------|---------|
| Risk per trade | 0.5% of account |
| Max daily loss | 1.5% of account (trips kill switch) |
| Max open positions | 2 |
| Max correlated positions | 1 (per `beta_group`, e.g. `btc_beta`) |
| Leverage | **disabled** (`allow_leverage=false`, `max_leverage=1`) |
| Live trading | **disabled** (no shipped adapter) |
| Stop loss | **mandatory** on every trade |
| Take profit | required; `>=` stop distance unless explicitly disabled |
| Min stop distance | 0.3% of price |

## Position sizing ([`position_sizing.py`](backend/app/risk/position_sizing.py))
Size is derived from dollar risk, never a fixed notional:
```
target_risk   = account_size * risk_per_trade
size          = target_risk / |entry - stop|
notional      = size * entry
```
With leverage disabled, `notional` is capped at the account size (which only *reduces* risk
below target). Orders below an asset's min notional are rejected.

## Stops & take-profit
- [`stop_engine.py`](backend/app/risk/stop_engine.py): the wider (safer) of an ATR stop and
  the structural invalidation level, on the correct side of entry, never tighter than the
  minimum distance.
- [`take_profit_engine.py`](backend/app/risk/take_profit_engine.py): at least
  `min_reward_risk_ratio` × the stop distance; a forecast target (q90/q10 price) may push it
  further out but never closer.

## Exposure limits & the coordinator ([`exposure_limits.py`](backend/app/risk/exposure_limits.py))
`assess_trade(...)` checks, in order, and returns a reason-coded decision:
1. kill switch active → `risk_kill_switch_active`
2. daily loss limit breached → `risk_daily_loss_limit`
3. max open positions → `risk_max_open_positions`
4. correlated exposure (same `beta_group`) → `risk_max_correlated`
5. compute mandatory stop; reject if too tight → `risk_stop_too_tight`
6. compute take-profit; reject if R:R too low → `risk_reward_risk_too_low`
7. size; reject if below min notional → `risk_size_below_min_notional`
8. otherwise → allowed, with size/stop/take-profit/risk amount.

## Kill switch ([`kill_switch.py`](backend/app/risk/kill_switch.py))
Trips on: N consecutive losing trades in a day, a data-provider error, model uncertainty
above threshold, or spread above threshold; the daily-loss breach also halts entries. State
is persisted as active `risk_events` (survives restarts) and auto-clears after
`cooldown_minutes`. Pure predicate helpers (`exceeds_consecutive_losses`,
`exceeds_uncertainty`, `exceeds_spread`) are unit-tested.

## Invariants (also AGENTS.md)
- No position without a stop.
- No leverage by default.
- No live trading.
- Every risk decision carries a reason code.
- Returns are reported net of costs.
