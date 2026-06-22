"""Market-structure entry confirmation.

Kronos chooses the battlefield; market structure chooses the entry. A directional
forecast is necessary but not sufficient — we require at least one structural
trigger and a sane (non-late) entry before a candidate becomes actionable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.core.constants import Side
from app.strategy import volatility_engine as ind


@dataclass
class StructureResult:
    side: Side
    confirmed: bool
    conditions_met: list[str] = field(default_factory=list)
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    invalidation_level: float | None = None
    distance_atr: float = 0.0
    late_entry: bool = False
    atr: float = 0.0


def evaluate_structure(
    df: pd.DataFrame, side: Side, *, late_entry_atr_multiple: float = 1.5
) -> StructureResult:
    """Check structural entry triggers for a given side and locate the entry zone."""
    price = float(df["close"].iloc[-1])
    atr_series = ind.atr(df, 14)
    atr_val = float(atr_series.iloc[-1]) if not atr_series.dropna().empty else price * 0.01
    ema50 = ind.ema(df["close"], 50)
    vwap = ind.rolling_vwap(df, 24)
    vwap_val = float(vwap.iloc[-1])
    ema50_val = float(ema50.iloc[-1])
    struct = ind.structure_flags(df)
    vol_exp = ind.volume_expansion(df)

    lookback = df.iloc[-48:] if len(df) >= 48 else df
    range_high = float(lookback["high"].max())
    range_low = float(lookback["low"].min())

    conditions: list[str] = []

    if side == Side.LONG:
        if abs(price - vwap_val) <= atr_val and price >= ema50_val:
            conditions.append("pullback_to_vwap")
        if price > range_high - atr_val and struct["higher_high"]:
            conditions.append("breakout_retest")
        if struct["higher_low"]:
            conditions.append("higher_low_confirmation")
        if price > ema50_val and float(df["close"].iloc[-2]) <= float(ema50.iloc[-2]):
            conditions.append("ema_reclaim")
        if price >= range_high and vol_exp >= 1.2:
            conditions.append("range_breakout_volume")

        entry_low = max(ema50_val, vwap_val - atr_val)
        entry_high = vwap_val + atr_val
        invalidation = range_low - atr_val
    else:  # SHORT (inverse conditions)
        if abs(price - vwap_val) <= atr_val and price <= ema50_val:
            conditions.append("rally_to_vwap")
        if price < range_low + atr_val and struct["lower_low"]:
            conditions.append("breakdown_retest")
        if struct["lower_high"]:
            conditions.append("lower_high_confirmation")
        if price < ema50_val and float(df["close"].iloc[-2]) >= float(ema50.iloc[-2]):
            conditions.append("ema_loss")
        if price <= range_low and vol_exp >= 1.2:
            conditions.append("range_breakdown_volume")

        entry_low = vwap_val - atr_val
        entry_high = min(ema50_val, vwap_val + atr_val)
        invalidation = range_high + atr_val

    # late entry: how far is price from the entry zone, in ATRs?
    zone_mid = (entry_low + entry_high) / 2.0
    distance_atr = abs(price - zone_mid) / atr_val if atr_val > 0 else 0.0
    late = distance_atr > late_entry_atr_multiple

    return StructureResult(
        side=side,
        confirmed=len(conditions) > 0 and not late,
        conditions_met=conditions,
        entry_zone_low=round(entry_low, 8),
        entry_zone_high=round(entry_high, 8),
        invalidation_level=round(invalidation, 8),
        distance_atr=round(distance_atr, 3),
        late_entry=late,
        atr=atr_val,
    )
