# Skill: Quant research

How to add and judge factors/strategies in this codebase without fooling yourself.

## How to design factors
- Derive factors only from data available **before** the decision time. Build them on a
  trailing window of the candle frame (see `app/strategy/volatility_engine.py`).
- Put every threshold/weight in `configs/strategy.default.json`; never hardcode. Bump
  `edge_formula_version` when the formula changes.
- Prefer interpretable, bounded factors (probabilities, ratios in known ranges) so they
  combine cleanly in the edge score.

## How to avoid leakage
- Never use the current or future candle's close to decide the current entry.
- In backtests, the simulator hands you `df.iloc[:i+1]`; entries fill at the next open.
  Don't reach outside the slice.
- Don't fit parameters on the same window you evaluate on.

## How to judge signal quality
- Look at `edge_score`, `cost_adjusted_edge`, `asymmetry_score`, `path_quality`,
  `forecast_volatility_ratio`, and `uncertainty_score` together — not probability alone.
- A high p_up with poor asymmetry or high uncertainty is not an edge.

## How to compare to baselines
- Always run the backtest baselines (buy&hold, EMA trend, ATR breakout, random).
- Judge on **risk-adjusted** metrics (Sharpe, profit factor, max drawdown) **after costs**.

## How to reject weak strategies
- If it doesn't beat baselines on Sharpe AND profit factor after fees+slippage, reject it.
- If results hinge on a handful of trades or one regime, treat as not robust.
- Mock-mode results are for plumbing only — never claim edge from mock forecasts.
