# SIGNAL_SPEC.md — Signal scoring & edge formula

Implemented in [`app/strategy/signal_scoring.py`](backend/app/strategy/signal_scoring.py).
All thresholds live in [`configs/strategy.default.json`](configs/strategy.default.json) and
are versioned by `edge_formula_version` (currently `v1`). **No raw buy/sell labels** —
every asset gets a status and reason codes.

## Per-asset computed factors
- `p_up_24h`, `p_down_24h` — fraction of forecast paths ending up / down.
- `median_return`, `q10_return`, `q90_return` — terminal-return quantiles.
- `asymmetry_score` — upside vs downside (see formula).
- `forecast_volatility_ratio` — forecast vol ÷ recent realized vol.
- `path_quality` — directional consistency + linearity (R²) of the median path, in [0,1].
- `trend_alignment` — +1 aligned regime, 0 neutral, −1 opposing.
- `regime_score` — regime classifier confidence (0 if regime blocks the side).
- `liquidity_score` — 0..1 turnover-stability proxy.
- `cost_adjusted_edge` — expected directional return minus round-trip fees + slippage.
- `edge_score` — the headline score (below).
- `confidence_label` — high / medium / low / none from probability bands.
- `trade_candidate_status` — one of the statuses below.

## Trade candidate statuses
`no_edge`, `watch`, `long_candidate`, `short_candidate`, `blocked_by_regime`,
`blocked_by_risk`, `blocked_by_late_entry`, `blocked_by_costs`, `blocked_by_uncertainty`.
(`blocked_by_risk` is set by the risk engine at order/backtest time.)

## Edge formula v1
For a **long**:
```
direction_score    = p_up - 0.5
asymmetry_score    = max(q90_return, 0) / max(|q10_return|, tiny)
cost_adjusted_edge = median_return - round_trip_cost            # round_trip_cost = 2*(fee_bps+slippage_bps)/1e4
volatility_penalty = penalty_scale * max(0, vol_ratio - penalty_threshold)
edge_score         = direction_score * asymmetry_score * path_quality * regime_score
                     - volatility_penalty
```
For a **short**, the directional logic inverts:
```
direction_score    = p_down - 0.5
asymmetry_score    = max(-q10_return, 0) / max(q90_return, tiny)
cost_adjusted_edge = (-median_return) - round_trip_cost
```

## Gating order (first failing gate wins; blocks beat watch)
1. `vol_ratio > maximum_volatility_ratio` OR `uncertainty > 0.85` → **blocked_by_uncertainty**
2. `require_regime_alignment` and regime opposes side → **blocked_by_regime**
3. `cost_adjusted_edge < minimum_cost_adjusted_edge` → **blocked_by_costs**
4. structure says late entry → **blocked_by_late_entry**
5. `asymmetry < minimum_asymmetry` → **watch**
6. `path_quality < minimum_path_quality` → **watch**
7. `require_market_structure_confirmation` and not confirmed → **watch**
8. `edge_score < minimum_edge_score` → **watch**
9. otherwise → **long_candidate / short_candidate**

If neither `p_up >= minimum_p_up` nor `p_down >= minimum_p_down`, status is **no_edge**.

## Market structure (entry)
Kronos picks direction; structure picks the entry. Implemented in
[`market_structure.py`](backend/app/strategy/market_structure.py). A long requires at least
one of: pullback to VWAP, breakout retest, higher-low confirmation, EMA reclaim, range
breakout with volume. Shorts use the inverse. If price is more than
`late_entry_atr_multiple` ATRs from the entry zone → late entry (blocked).

## Regime engine
[`regime_detector.py`](backend/app/strategy/regime_detector.py) classifies
`trend_up / trend_down / range / volatility_expansion / panic / unknown` using EMA50/EMA200,
realized-vol ratio, volume expansion, VWAP distance and HH/LL structure, and returns a
human-readable explanation, e.g.:
> "BTC is above EMA200 with EMA50>EMA200 and making higher lows. Regime is trend_up."

For crypto, the BTC benchmark regime is computed first and passed as the market filter.

## Explanations
Each signal stores per-factor explanation rows (`signal_explanations`) with value, threshold
and pass/fail, so the UI can show *why* a candidate is or isn't actionable.
