"""Take-profit placement.

TP must be at least ``min_reward_risk_ratio`` x the stop distance (unless
explicitly disabled in config). A forecast target (e.g. the q90 price) may push
the TP further out but never closer than the minimum R:R.
"""

from __future__ import annotations

from app.core.constants import Side


def compute_take_profit(
    *,
    side: Side,
    entry: float,
    stop: float,
    min_reward_risk_ratio: float = 1.0,
    forecast_target: float | None = None,
) -> float:
    dist = abs(entry - stop)
    min_tp = entry + min_reward_risk_ratio * dist if side == Side.LONG else entry - min_reward_risk_ratio * dist

    if forecast_target is not None:
        if side == Side.LONG:
            tp = max(min_tp, forecast_target)
        else:
            tp = min(min_tp, forecast_target)
    else:
        tp = min_tp
    return round(tp, 8)


def reward_risk_ratio(side: Side, entry: float, stop: float, take_profit: float) -> float:
    risk = abs(entry - stop)
    reward = abs(take_profit - entry)
    return reward / risk if risk > 0 else 0.0
