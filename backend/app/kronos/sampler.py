"""Sample-path generation for both backends.

- Mock: a deterministic geometric-Brownian-motion simulation seeded from the
  recent drift + realized volatility of the context. Clearly labeled MOCK and
  never confused with real model output.
- Real: collects ``sample_count`` independent paths by calling the verified
  upstream ``predict(..., sample_count=1)`` repeatedly (upstream averages its own
  internal samples, so one call == one path for our purposes).
"""

from __future__ import annotations

import hashlib

import numpy as np

from app.config import KronosConfig
from app.core.errors import ModelLoadError
from app.kronos.feature_builder import ModelContext
from app.kronos.loader import KronosHandles
from app.logging_config import get_logger

log = get_logger("kronos.sampler")


def _seed_from_context(symbol: str, ctx: ModelContext) -> int:
    raw = f"{symbol}|{ctx.context_end.isoformat()}|{ctx.horizon}".encode()
    return int(hashlib.sha256(raw).hexdigest(), 16) % (2**32)


def generate_mock_paths(symbol: str, ctx: ModelContext, config: KronosConfig) -> np.ndarray:
    """Deterministic GBM mock forecast. Returns [sample_count, horizon] close prices."""
    rng = np.random.default_rng(_seed_from_context(symbol, ctx))
    s, h = config.sample_count, ctx.horizon

    log_ret = np.diff(np.log(ctx.df["close"].to_numpy(dtype=float)))
    # damp the drift so mock mode does not manufacture a strong trend signal
    mu = float(np.mean(log_ret[-min(len(log_ret), 72):])) * 0.3 if log_ret.size else 0.0
    sigma = max(ctx.realized_volatility, 1e-6)

    shocks = rng.normal(loc=mu, scale=sigma, size=(s, h))
    cum = np.cumsum(shocks, axis=1)
    paths = ctx.last_close * np.exp(cum)
    return paths


def generate_real_paths(
    handles: KronosHandles, ctx: ModelContext, config: KronosConfig
) -> np.ndarray:
    """Collect sample_count independent close-price paths from the real model."""
    cols = ["open", "high", "low", "close", "volume", "amount"]
    df = ctx.df[cols]

    paths: list[np.ndarray] = []
    for i in range(config.sample_count):
        try:
            pred_df = handles.predictor.predict(
                df=df,
                x_timestamp=ctx.x_timestamp,
                y_timestamp=ctx.y_timestamp,
                pred_len=ctx.horizon,
                T=config.temperature,
                top_k=config.top_k,
                top_p=config.top_p,
                sample_count=1,
                verbose=False,
            )
        except Exception as exc:  # pragma: no cover - depends on real model
            raise ModelLoadError(f"Kronos predict() failed on sample {i}: {exc}") from exc

        close = np.asarray(pred_df["close"].to_numpy(), dtype=float)
        if close.shape[0] != ctx.horizon:
            raise ModelLoadError(
                f"Kronos returned {close.shape[0]} steps, expected {ctx.horizon}"
            )
        paths.append(close)

    return np.vstack(paths)
