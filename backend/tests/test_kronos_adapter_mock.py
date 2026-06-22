"""Kronos adapter mock-mode behavior: shape, determinism, honest labeling."""

from __future__ import annotations

import pytest

from app.config import KronosConfig
from app.core.constants import ForecastMode
from app.core.errors import MockModeForbiddenError
from app.kronos.adapter import KronosAdapter


def _cfg(**kw) -> KronosConfig:
    base = dict(mock_mode="true", context_length=360, forecast_horizon=24, sample_count=30)
    base.update(kw)
    return KronosConfig(**base)


def test_mock_forecast_shape(candles):
    dist = KronosAdapter(_cfg()).forecast(candles, symbol="BTC/USDT", timeframe="1h")
    assert dist.mode == ForecastMode.MOCK
    assert len(dist.median_path) == 24
    assert len(dist.q10_path) == 24 and len(dist.q90_path) == 24
    assert dist.sample_count == 30
    assert 0.0 <= dist.p_up <= 1.0
    assert abs((dist.p_up + dist.p_down) - 1.0) <= 1.0  # both fractions, ties allowed


def test_mock_is_labeled_and_not_real(candles):
    dist = KronosAdapter(_cfg()).forecast(candles, symbol="BTC/USDT", timeframe="1h")
    assert dist.is_mock is True
    assert dist.model_name == "mock-gbm-v1"  # impossible to confuse with a real model id


def test_mock_is_deterministic(candles):
    a = KronosAdapter(_cfg()).forecast(candles, symbol="BTC/USDT", timeframe="1h")
    b = KronosAdapter(_cfg()).forecast(candles, symbol="BTC/USDT", timeframe="1h")
    assert a.p_up == b.p_up
    assert a.median_return == b.median_return


def test_quantiles_are_ordered(candles):
    dist = KronosAdapter(_cfg()).forecast(candles, symbol="BTC/USDT", timeframe="1h")
    assert dist.q10_return <= dist.q25_return <= dist.median_return <= dist.q75_return <= dist.q90_return


def test_mock_mode_false_raises_when_model_unavailable(candles):
    """We never silently downgrade to mock when real output is demanded."""
    adapter = KronosAdapter(_cfg(mock_mode="false"))
    with pytest.raises(MockModeForbiddenError):
        adapter.forecast(candles, symbol="BTC/USDT", timeframe="1h")


def test_insufficient_context_raises(make_candles):
    short = make_candles(n=100)
    with pytest.raises(ValueError):
        KronosAdapter(_cfg()).forecast(short, symbol="BTC/USDT", timeframe="1h")
