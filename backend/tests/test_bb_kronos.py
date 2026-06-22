"""Deterministic tests for Bollinger Bands + the BB+Kronos plan logic (no GPU/model)."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

from app.core.constants import Side
from app.strategy import bb_kronos as bk
from app.strategy import volatility_engine as ind


def _df(closes: list[float]) -> pd.DataFrame:
    n = len(closes)
    c = np.array(closes, dtype=float)
    idx = pd.date_range("2025-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"open": c, "high": c * 1.001, "low": c * 0.999, "close": c,
                         "volume": np.ones(n)}, index=idx)


def _fc(last_close, q10, q90, median, unc=0.5):
    return SimpleNamespace(last_close=last_close, q10_return=q10, q90_return=q90,
                           median_return=median, uncertainty_score=unc)


def test_bollinger_bands_math():
    df = _df([100.0] * 30)  # constant → std 0 → bands collapse to mid
    bb = ind.bollinger_bands(df["close"], period=20, k=2.0)
    assert abs(bb["mid"].iloc[-1] - 100.0) < 1e-9
    assert abs(bb["upper"].iloc[-1] - bb["lower"].iloc[-1]) < 1e-9  # zero width


def test_squeeze_percentile_bounds():
    rng = np.random.default_rng(1)
    closes = list(100 + np.cumsum(rng.normal(0, 0.5, 200)))
    p = ind.bb_squeeze_percentile(pd.Series(closes), 20, 2.0, 120)
    assert 0.0 <= p <= 1.0


def _compression_then_breakout(seed=7):
    """Normal-vol baseline, then genuine compression (minority of lookback), then a breakout bar."""
    rng = np.random.default_rng(seed)
    normal = list(100 + np.cumsum(rng.normal(0, 0.6, 235)))
    lvl = normal[-1]
    squeeze = list(lvl + rng.normal(0, 0.02, 15))  # real squeeze
    return _df(normal + squeeze + [lvl + 5.0])      # decisive breakout above the band


def test_squeeze_breakout_fires_on_compression_then_breakout():
    df = _compression_then_breakout()
    fc = _fc(last_close=float(df["close"].iloc[-1]), q10=-0.02, q90=0.05, median=0.03)
    plan = bk.squeeze_breakout_plan(fc, df)
    assert plan is not None and plan.side == Side.LONG
    assert "bb_squeeze" in plan.reason_codes


def test_squeeze_breakout_skips_when_kronos_expects_small_move():
    df = _compression_then_breakout()
    fc = _fc(last_close=float(df["close"].iloc[-1]), q10=-0.001, q90=0.001, median=0.0)  # spread ~0
    assert bk.squeeze_breakout_plan(fc, df) is None


def test_mean_reversion_long_fade_below_lower_band():
    rng = np.random.default_rng(2)
    closes = list(100 + rng.normal(0, 0.3, 199)) + [90.0]  # last bar crashes below lower band
    df = _df(closes)
    fc = _fc(last_close=90.0, q10=-0.01, q90=0.02, median=0.0)  # Kronos neutral → no veto
    plan = bk.mean_reversion_fade_plan(fc, df)
    assert plan is not None and plan.side == Side.LONG
    assert "mean_reversion_fade" in plan.reason_codes


def test_mean_reversion_vetoed_when_kronos_predicts_continued_drop():
    rng = np.random.default_rng(2)
    closes = list(100 + rng.normal(0, 0.3, 199)) + [90.0]
    df = _df(closes)
    fc = _fc(last_close=90.0, q10=-0.05, q90=0.0, median=-0.03)  # Kronos: keeps falling → veto
    assert bk.mean_reversion_fade_plan(fc, df) is None
