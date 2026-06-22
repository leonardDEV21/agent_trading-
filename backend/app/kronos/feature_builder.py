"""Prepare model context from stored candles.

Builds the exact inputs the verified Kronos API needs:
- df with columns [open, high, low, close, volume, amount]
- x_timestamp: historical candle-open timestamps
- y_timestamp: future candle-open timestamps (horizon)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from app.core.timeframes import future_timestamps


@dataclass
class ModelContext:
    df: pd.DataFrame  # OHLCV+amount, length == context_length
    x_timestamp: pd.Series
    y_timestamp: pd.Series
    last_close: float
    realized_volatility: float
    context_start: datetime
    context_end: datetime
    horizon: int


def prepare_context(df: pd.DataFrame, *, timeframe: str, context_length: int, horizon: int) -> ModelContext:
    """Slice the trailing ``context_length`` candles and compute future timestamps.

    ``df`` must be a UTC-indexed OHLCV(+amount) DataFrame sorted ascending.
    """
    if df.empty:
        raise ValueError("Cannot prepare context from empty candle frame")
    if len(df) < context_length:
        raise ValueError(
            f"Not enough candles for context: have {len(df)}, need {context_length}"
        )

    ctx = df.iloc[-context_length:].copy()
    if "amount" not in ctx.columns:
        ctx["amount"] = ctx["close"] * ctx["volume"]

    x_timestamp = pd.Series(ctx.index)
    last_open = ctx.index[-1].to_pydatetime()
    y_ts = future_timestamps(last_open, timeframe, horizon)
    y_timestamp = pd.Series(y_ts)

    last_close = float(ctx["close"].iloc[-1])
    pct_returns = ctx["close"].pct_change().dropna()
    realized_volatility = float(pct_returns.std()) if len(pct_returns) > 1 else 0.0

    return ModelContext(
        df=ctx,
        x_timestamp=x_timestamp,
        y_timestamp=y_timestamp,
        last_close=last_close,
        realized_volatility=max(realized_volatility, 1e-9),
        context_start=ctx.index[0].to_pydatetime(),
        context_end=last_open,
        horizon=horizon,
    )


def context_close_array(ctx: ModelContext) -> np.ndarray:
    return ctx.df["close"].to_numpy(dtype=float)
