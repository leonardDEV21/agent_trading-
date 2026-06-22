"""Shared test fixtures."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("KAT_MOCK_MODE", "true")


def _make_candles(n: int = 800, seed: int = 7, drift: float = 0.0005, vol: float = 0.01) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    idx = pd.DatetimeIndex([start + timedelta(hours=i) for i in range(n)])
    shocks = rng.normal(drift, vol, n)
    close = 30000 * np.exp(np.cumsum(shocks))
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum.reduce([close, open_]) * (1 + np.abs(rng.normal(0, 0.003, n)))
    low = np.minimum.reduce([close, open_]) * (1 - np.abs(rng.normal(0, 0.003, n)))
    volume = rng.uniform(50, 200, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "volume": volume, "amount": close * volume},
        index=idx,
    )


@pytest.fixture
def candles() -> pd.DataFrame:
    return _make_candles()


@pytest.fixture
def uptrend_candles() -> pd.DataFrame:
    return _make_candles(drift=0.002, vol=0.006, seed=11)


@pytest.fixture
def make_candles():
    return _make_candles
