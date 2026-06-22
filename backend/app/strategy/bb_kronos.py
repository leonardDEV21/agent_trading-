"""BB + Kronos strategy candidates (research, paper-only).

Premise (from the edge audit): Kronos-base has weak *direction* skill but its
forecast carries *magnitude* information (Pearson IC >> Spearman). So Kronos is used
here as a volatility filter/veto, never as the direction picker — Bollinger Bands
provide timing and direction. Two setups:

  A. squeeze_breakout_plan   — BB squeeze + Kronos expects a large move + band breakout.
  B. mean_reversion_fade_plan — price beyond a band, faded back to the mean, UNLESS
                                Kronos predicts a large continued move that way (veto).

Both return a simulator.TradePlan (or None). The HARD STOP is still set by the risk
engine from atr/invalidation — this module never weakens risk discipline. These are
gated behind the spread-validation premise (see scripts/run_bb_kronos_backtest.py):
if Kronos cannot predict move SIZE, neither setup should be traded.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.backtesting.simulator import TradePlan
from app.core.constants import Side
from app.kronos.forecast_postprocessor import ForecastDistribution
from app.strategy import volatility_engine as ind


@dataclass
class BBKronosParams:
    bb_period: int = 20
    bb_k: float = 2.0
    squeeze_lookback: int = 120
    squeeze_threshold: float = 0.25      # squeeze if width percentile <= this
    min_predicted_spread: float = 0.02   # Kronos must expect >=2% (q90-q10) to confirm expansion
    fade_veto_return: float = 0.01       # veto a fade if |median_return| exceeds this against it
    atr_period: int = 14
    stop_atr_mult: float = 1.5


def _ready(df: pd.DataFrame, params: BBKronosParams) -> bool:
    return len(df) >= max(params.bb_period, params.atr_period, params.squeeze_lookback) + 2


def squeeze_breakout_plan(
    forecast: ForecastDistribution, df: pd.DataFrame, params: BBKronosParams | None = None
) -> TradePlan | None:
    """A: trade a band breakout only during a squeeze that Kronos expects to expand."""
    params = params or BBKronosParams()
    if not _ready(df, params):
        return None
    close = df["close"]
    bb = ind.bollinger_bands(close, params.bb_period, params.bb_k)
    # Measure the squeeze and the band on the bars BEFORE the current (breakout) candle —
    # otherwise the breakout bar inflates its own std and masks the squeeze. Still
    # no-lookahead: everything used has already closed.
    upper, lower = float(bb["upper"].iloc[-2]), float(bb["lower"].iloc[-2])
    if pd.isna(upper) or pd.isna(lower):
        return None

    squeeze_pct = ind.bb_squeeze_percentile(close.iloc[:-1], params.bb_period, params.bb_k,
                                            params.squeeze_lookback)
    predicted_spread = float(forecast.q90_return - forecast.q10_return)
    if squeeze_pct > params.squeeze_threshold:
        return None  # not compressed before this bar → no breakout edge
    if predicted_spread < params.min_predicted_spread:
        return None  # Kronos does NOT expect a large move → skip the breakout

    cur = float(close.iloc[-1])
    if cur > upper:
        side = Side.LONG
    elif cur < lower:
        side = Side.SHORT
    else:
        return None  # squeeze present but no breakout yet

    atr_val = float(ind.atr(df, params.atr_period).iloc[-1])
    if pd.isna(atr_val) or atr_val <= 0:
        return None
    if side == Side.LONG:
        invalidation = cur - params.stop_atr_mult * atr_val
        target = forecast.last_close * (1 + forecast.q90_return)
    else:
        invalidation = cur + params.stop_atr_mult * atr_val
        target = forecast.last_close * (1 + forecast.q10_return)

    return TradePlan(
        side=side, atr=atr_val, invalidation_level=invalidation, forecast_target=target,
        regime="volatility_expansion",
        reason_codes=["bb_squeeze", "kronos_expansion_confirmed", "bb_band_breakout"],
        uncertainty=forecast.uncertainty_score,
    )


def mean_reversion_fade_plan(
    forecast: ForecastDistribution, df: pd.DataFrame, params: BBKronosParams | None = None
) -> TradePlan | None:
    """B: fade a band excursion back toward the mean, unless Kronos vetoes (real breakout)."""
    params = params or BBKronosParams()
    if not _ready(df, params):
        return None
    close = df["close"]
    bb = ind.bollinger_bands(close, params.bb_period, params.bb_k)
    pct_b = float(bb["pct_b"].iloc[-1])
    mid = float(bb["mid"].iloc[-1])
    if pd.isna(pct_b) or pd.isna(mid):
        return None

    atr_val = float(ind.atr(df, params.atr_period).iloc[-1])
    if pd.isna(atr_val) or atr_val <= 0:
        return None
    cur = float(close.iloc[-1])
    median = float(forecast.median_return)

    if pct_b < 0.0:  # below lower band → long fade
        if median < -params.fade_veto_return:
            return None  # Kronos says it keeps falling → don't catch the knife
        side = Side.LONG
        invalidation = cur - params.stop_atr_mult * atr_val
    elif pct_b > 1.0:  # above upper band → short fade
        if median > params.fade_veto_return:
            return None  # Kronos says it keeps rising → don't fade a real breakout
        side = Side.SHORT
        invalidation = cur + params.stop_atr_mult * atr_val
    else:
        return None  # inside the bands → no fade

    return TradePlan(
        side=side, atr=atr_val, invalidation_level=invalidation, forecast_target=mid,
        regime="range",
        reason_codes=["bb_band_excursion", "mean_reversion_fade", "kronos_veto_passed"],
        uncertainty=forecast.uncertainty_score,
    )


PLANS = {"squeeze_breakout": squeeze_breakout_plan, "mean_reversion_fade": mean_reversion_fade_plan}
