"""Turn raw Kronos sample paths into a probabilistic ForecastDistribution.

The upstream Kronos.predict() averages its internal samples, so to obtain a
*distribution* the adapter collects ``sample_count`` independent close-price
paths (shape [S, horizon]) and this module derives all quantiles and summary
statistics from them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from app.core.constants import ForecastMode


@dataclass
class ForecastDistribution:
    """Full forecast output (mirrors the schema in PRD / SIGNAL_SPEC)."""

    symbol: str
    timeframe: str
    created_at: datetime
    context_start: datetime
    context_end: datetime
    horizon: int
    sample_count: int
    mode: ForecastMode
    model_name: str
    model_config_hash: str
    last_close: float

    # per-step quantile paths (length == horizon), price space
    median_path: list[float] = field(default_factory=list)
    q10_path: list[float] = field(default_factory=list)
    q25_path: list[float] = field(default_factory=list)
    q75_path: list[float] = field(default_factory=list)
    q90_path: list[float] = field(default_factory=list)
    # raw sample paths (capped before storage)
    forecast_paths: list[list[float]] = field(default_factory=list)

    # terminal-return distribution (fraction, e.g. 0.012 == +1.2%)
    p_up: float = 0.5
    p_down: float = 0.5
    median_return: float = 0.0
    q10_return: float = 0.0
    q25_return: float = 0.0
    q75_return: float = 0.0
    q90_return: float = 0.0

    forecast_volatility: float = 0.0
    forecast_volatility_ratio: float = 1.0
    uncertainty_score: float = 0.0

    @property
    def is_mock(self) -> bool:
        return self.mode == ForecastMode.MOCK

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "created_at": self.created_at,
            "context_start": self.context_start,
            "context_end": self.context_end,
            "horizon": self.horizon,
            "sample_count": self.sample_count,
            "mode": self.mode.value,
            "model_name": self.model_name,
            "model_config_hash": self.model_config_hash,
            "last_close": self.last_close,
            "median_path": self.median_path,
            "q10_path": self.q10_path,
            "q25_path": self.q25_path,
            "q75_path": self.q75_path,
            "q90_path": self.q90_path,
            "forecast_paths": self.forecast_paths,
            "p_up": self.p_up,
            "p_down": self.p_down,
            "median_return": self.median_return,
            "q10_return": self.q10_return,
            "q25_return": self.q25_return,
            "q75_return": self.q75_return,
            "q90_return": self.q90_return,
            "forecast_volatility": self.forecast_volatility,
            "forecast_volatility_ratio": self.forecast_volatility_ratio,
            "uncertainty_score": self.uncertainty_score,
        }


def build_distribution(
    *,
    sample_paths: np.ndarray,
    last_close: float,
    realized_volatility: float,
    symbol: str,
    timeframe: str,
    context_start: datetime,
    context_end: datetime,
    created_at: datetime,
    horizon: int,
    mode: ForecastMode,
    model_name: str,
    model_config_hash: str,
    max_stored_paths: int = 50,
) -> ForecastDistribution:
    """Compute the full distribution from sample paths (close prices).

    ``sample_paths`` shape: [sample_count, horizon].
    ``realized_volatility``: std of per-step pct returns over the context window.
    """
    if sample_paths.ndim != 2:
        raise ValueError(f"sample_paths must be 2D [S, horizon], got shape {sample_paths.shape}")
    s_count, h = sample_paths.shape
    if h != horizon:
        raise ValueError(f"sample_paths horizon {h} != requested horizon {horizon}")

    # terminal returns per sample
    terminal = sample_paths[:, -1]
    terminal_returns = terminal / last_close - 1.0

    eps = 1e-12
    p_up = float(np.mean(terminal_returns > 0))
    p_down = float(np.mean(terminal_returns < 0))

    def q(arr: np.ndarray, pct: float) -> float:
        return float(np.quantile(arr, pct))

    median_return = float(np.median(terminal_returns))
    q10_return, q25_return = q(terminal_returns, 0.10), q(terminal_returns, 0.25)
    q75_return, q90_return = q(terminal_returns, 0.75), q(terminal_returns, 0.90)

    # per-step quantile paths
    median_path = np.median(sample_paths, axis=0)
    q10_path = np.quantile(sample_paths, 0.10, axis=0)
    q25_path = np.quantile(sample_paths, 0.25, axis=0)
    q75_path = np.quantile(sample_paths, 0.75, axis=0)
    q90_path = np.quantile(sample_paths, 0.90, axis=0)

    # within-path volatility, averaged across samples
    step_returns = np.diff(sample_paths, axis=1) / (sample_paths[:, :-1] + eps)
    per_path_vol = np.std(step_returns, axis=1)
    forecast_volatility = float(np.mean(per_path_vol)) if per_path_vol.size else 0.0
    forecast_volatility_ratio = (
        forecast_volatility / realized_volatility if realized_volatility > eps else 1.0
    )

    # bounded uncertainty score in [0, 1]: dispersion vs signal (coeff-of-variation style)
    std_terminal = float(np.std(terminal_returns))
    uncertainty_score = float(
        np.clip(std_terminal / (abs(median_return) + std_terminal + eps), 0.0, 1.0)
    )

    return ForecastDistribution(
        symbol=symbol,
        timeframe=timeframe,
        created_at=created_at,
        context_start=context_start,
        context_end=context_end,
        horizon=horizon,
        sample_count=s_count,
        mode=mode,
        model_name=model_name,
        model_config_hash=model_config_hash,
        last_close=float(last_close),
        median_path=[float(x) for x in median_path],
        q10_path=[float(x) for x in q10_path],
        q25_path=[float(x) for x in q25_path],
        q75_path=[float(x) for x in q75_path],
        q90_path=[float(x) for x in q90_path],
        forecast_paths=[[float(x) for x in p] for p in sample_paths[:max_stored_paths]],
        p_up=p_up,
        p_down=p_down,
        median_return=median_return,
        q10_return=q10_return,
        q25_return=q25_return,
        q75_return=q75_return,
        q90_return=q90_return,
        forecast_volatility=forecast_volatility,
        forecast_volatility_ratio=forecast_volatility_ratio,
        uncertainty_score=uncertainty_score,
    )
