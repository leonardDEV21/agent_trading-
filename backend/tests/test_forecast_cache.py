"""The forecast cache must be exact (identical result) and actually hit on re-run."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import get_config_store
from app.kronos import forecast_cache as fcache
from app.kronos.adapter import KronosAdapter


def _df(n=420):
    rng = np.random.default_rng(3)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    idx = pd.date_range("2025-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({
        "open": np.concatenate([[close[0]], close[:-1]]),
        "high": close * 1.002, "low": close * 0.998, "close": close,
        "volume": rng.uniform(1, 5, n), "amount": close * rng.uniform(1, 5, n),
    }, index=idx)


def _mock_adapter():
    cfg = get_config_store().kronos().model_copy(update={"mock_mode": "true"})
    return KronosAdapter(cfg)


def test_cache_off_by_default(monkeypatch):
    monkeypatch.delenv("KAT_FORECAST_CACHE", raising=False)
    fcache.get_forecast_cache.cache_clear()
    assert fcache.get_forecast_cache() is None  # disabled → no behavior change


def test_cache_hit_returns_identical_result(tmp_path, monkeypatch):
    monkeypatch.setenv("KAT_FORECAST_CACHE", str(tmp_path / "fc.sqlite"))
    fcache.get_forecast_cache.cache_clear()
    cache = fcache.get_forecast_cache()
    assert cache is not None

    a = _mock_adapter()
    df = _df()
    first = a.forecast(df, symbol="BTC/USDT", timeframe="1h")
    assert cache.misses == 1 and cache.hits == 0

    second = a.forecast(df, symbol="BTC/USDT", timeframe="1h")
    assert cache.hits == 1, "second identical forecast must hit the cache"

    # exact-result: every scalar field identical
    for f in ["p_up", "p_down", "median_return", "q10_return", "q90_return",
              "last_close", "uncertainty_score", "forecast_volatility_ratio"]:
        assert getattr(first, f) == getattr(second, f)
    assert first.median_path == second.median_path
    assert first.mode == second.mode

    fcache.get_forecast_cache.cache_clear()
