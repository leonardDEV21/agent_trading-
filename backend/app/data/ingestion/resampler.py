"""Resample candles to a higher timeframe (e.g. 1h -> 4h) for regime context."""

from __future__ import annotations

import pandas as pd

from app.core.timeframes import timeframe_seconds


def resample_ohlcv(df: pd.DataFrame, from_tf: str, to_tf: str) -> pd.DataFrame:
    """Resample a UTC-indexed OHLCV DataFrame to a coarser timeframe.

    Requires ``to_tf`` to be a whole multiple of ``from_tf``. Uses standard OHLC
    aggregation (first/max/min/last) and summed volume/amount.
    """
    src = timeframe_seconds(from_tf)
    dst = timeframe_seconds(to_tf)
    if dst % src != 0:
        raise ValueError(f"{to_tf} is not a multiple of {from_tf}")
    if df.empty:
        return df.copy()

    rule = f"{dst}s"
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    if "amount" in df.columns:
        agg["amount"] = "sum"

    out = df.resample(rule, label="left", closed="left").agg(agg).dropna(subset=["open"])
    return out
