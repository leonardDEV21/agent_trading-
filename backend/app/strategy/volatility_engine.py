"""Technical indicators shared by the regime, structure and signal engines.

Pure pandas/numpy functions on UTC-indexed OHLCV frames. No model or DB deps.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return true_range(df).rolling(period, min_periods=period).mean()


def bollinger_bands(close: pd.Series, period: int = 20, k: float = 2.0) -> pd.DataFrame:
    """Bollinger Bands: middle SMA(period), upper/lower = middle ± k*std.

    Returns a frame with columns mid, upper, lower, width, pct_b. ``width`` is the
    band width normalized by the middle (a unitless squeeze gauge); ``pct_b`` is
    %B = (close - lower) / (upper - lower), where <0 is below the lower band and
    >1 is above the upper band. Uses a sample std (ddof=0) to match the classic
    definition. NaN until ``period`` candles are available (no lookahead).
    """
    mid = close.rolling(period, min_periods=period).mean()
    std = close.rolling(period, min_periods=period).std(ddof=0)
    upper = mid + k * std
    lower = mid - k * std
    span = (upper - lower).replace(0, np.nan)
    return pd.DataFrame({
        "mid": mid,
        "upper": upper,
        "lower": lower,
        "width": (upper - lower) / mid.replace(0, np.nan),
        "pct_b": (close - lower) / span,
    })


def bb_squeeze_percentile(close: pd.Series, period: int = 20, k: float = 2.0,
                          lookback: int = 120) -> float:
    """Where current BB width sits in its own recent distribution (0..1).

    0 = tightest squeeze in ``lookback``; 1 = widest. Low values flag compression
    that often precedes a volatility expansion. Returns 1.0 (no squeeze) when there
    is insufficient history.
    """
    bb = bollinger_bands(close, period, k)
    width = bb["width"].dropna()
    if len(width) < max(lookback // 2, period):
        return 1.0
    recent = width.iloc[-lookback:]
    cur = float(width.iloc[-1])
    return float((recent <= cur).mean())


def realized_volatility(close: pd.Series, window: int) -> float:
    """Std of per-step pct returns over the last ``window`` candles."""
    rets = close.pct_change().dropna()
    if len(rets) < 2:
        return 0.0
    return float(rets.iloc[-window:].std())


def rolling_vwap(df: pd.DataFrame, window: int = 24) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = (typical * df["volume"]).rolling(window, min_periods=1).sum()
    vol = df["volume"].rolling(window, min_periods=1).sum().replace(0, np.nan)
    return pv / vol


def volume_expansion(df: pd.DataFrame, short: int = 6, long: int = 48) -> float:
    """Ratio of recent average volume to longer-run average volume."""
    v = df["volume"]
    if len(v) < long:
        return 1.0
    s = v.iloc[-short:].mean()
    l = v.iloc[-long:].mean()
    return float(s / l) if l > 0 else 1.0


def structure_flags(df: pd.DataFrame, lookback: int = 10) -> dict[str, bool]:
    """Detect higher-highs/higher-lows and lower-highs/lower-lows structure."""
    if len(df) < lookback * 2:
        return {"higher_high": False, "higher_low": False, "lower_high": False, "lower_low": False}
    recent = df.iloc[-lookback:]
    prior = df.iloc[-2 * lookback:-lookback]
    return {
        "higher_high": bool(recent["high"].max() > prior["high"].max()),
        "higher_low": bool(recent["low"].min() > prior["low"].min()),
        "lower_high": bool(recent["high"].max() < prior["high"].max()),
        "lower_low": bool(recent["low"].min() < prior["low"].min()),
    }


def liquidity_score(df: pd.DataFrame, window: int = 168) -> float:
    """Crude 0..1 liquidity proxy from quote turnover stability.

    Higher when recent turnover is healthy and stable; lower when thin/erratic.
    """
    if "amount" in df.columns:
        turnover = df["amount"]
    else:
        turnover = df["close"] * df["volume"]
    recent = turnover.iloc[-window:]
    if recent.empty or recent.mean() <= 0:
        return 0.0
    cv = recent.std() / (recent.mean() + 1e-9)  # coefficient of variation
    return float(np.clip(1.0 / (1.0 + cv), 0.0, 1.0))
