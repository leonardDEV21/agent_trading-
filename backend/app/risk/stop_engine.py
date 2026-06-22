"""Stop-loss placement. Every paper/backtest trade MUST have a stop."""

from __future__ import annotations

from app.core.constants import Side


def compute_stop(
    *,
    side: Side,
    entry: float,
    atr: float,
    invalidation_level: float | None = None,
    atr_multiple: float = 1.5,
    min_stop_distance_pct: float = 0.003,
) -> float:
    """Return a stop price on the correct side of entry with a sane minimum distance.

    Uses the wider (safer) of an ATR stop and the structural invalidation level,
    then enforces ``min_stop_distance_pct`` so stops are never absurdly tight.
    """
    min_dist = entry * min_stop_distance_pct
    atr_dist = max(atr * atr_multiple, min_dist)

    if side == Side.LONG:
        stop = entry - atr_dist
        if invalidation_level is not None:
            stop = min(stop, invalidation_level)
        stop = min(stop, entry - min_dist)
    else:
        stop = entry + atr_dist
        if invalidation_level is not None:
            stop = max(stop, invalidation_level)
        stop = max(stop, entry + min_dist)

    return round(stop, 8)


def stop_distance(entry: float, stop: float) -> float:
    return abs(entry - stop)
