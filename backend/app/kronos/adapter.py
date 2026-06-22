"""The Kronos adapter — the ONLY entry point strategy/backtest code may use.

Responsibilities:
- Decide real vs mock mode honestly (never silently downgrade when real is
  demanded).
- Prepare context, generate sample paths, and post-process into a
  ForecastDistribution.

mock_mode semantics (from configs/kronos.default.json):
    "auto"  -> use real if it loads, else clearly-labeled mock
    "true"  -> always mock
    "false" -> require real; raise MockModeForbiddenError if it cannot load
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import KronosConfig, get_config_store
from app.core.constants import ForecastMode
from app.core.errors import ModelLoadError, MockModeForbiddenError
from app.core.timeframes import now_utc
from app.kronos.feature_builder import ModelContext, prepare_context
from app.kronos.forecast_postprocessor import ForecastDistribution, build_distribution
from app.kronos.predictor import RealForecaster
from app.kronos.sampler import generate_mock_paths
from app.logging_config import get_logger

log = get_logger("kronos.adapter")


class KronosAdapter:
    def __init__(self, config: KronosConfig):
        self.config = config
        self._real = RealForecaster(config)
        self._resolved_mode: ForecastMode | None = None

    # --- mode decision ------------------------------------------------------
    def resolve_mode(self) -> ForecastMode:
        """Determine the effective forecast mode. May raise MockModeForbiddenError."""
        setting = str(self.config.mock_mode).lower()
        if setting in {"true", "1", "yes"}:
            self._resolved_mode = ForecastMode.MOCK
            return ForecastMode.MOCK

        available, reason = self._real.available()
        if setting in {"false", "0", "no"}:
            if not available:
                raise MockModeForbiddenError(
                    f"mock_mode=false but the real Kronos model is unavailable: {reason}"
                )
            self._resolved_mode = ForecastMode.REAL
            return ForecastMode.REAL

        # auto
        mode = ForecastMode.REAL if available else ForecastMode.MOCK
        if mode == ForecastMode.MOCK:
            log.warning("kronos_falling_back_to_mock", reason=reason)
        self._resolved_mode = mode
        return mode

    # --- pipeline steps (match the spec's adapter surface) ------------------
    def prepare_context(self, df: pd.DataFrame, *, timeframe: str) -> ModelContext:
        return prepare_context(
            df,
            timeframe=timeframe,
            context_length=self.config.context_length,
            horizon=self.config.forecast_horizon,
        )

    def predict(self, ctx: ModelContext, symbol: str) -> tuple[np.ndarray, ForecastMode]:
        """Return (sample_paths [S, horizon], mode)."""
        mode = self.resolve_mode()
        if mode == ForecastMode.REAL:
            try:
                paths = self._real.sample_paths(ctx)
                return paths, ForecastMode.REAL
            except ModelLoadError:
                # Only auto mode may fall back here; false would have raised earlier.
                if str(self.config.mock_mode).lower() in {"false", "0", "no"}:
                    raise
                log.warning("kronos_runtime_fallback_to_mock", symbol=symbol)
                return generate_mock_paths(symbol, ctx, self.config), ForecastMode.MOCK
        return generate_mock_paths(symbol, ctx, self.config), ForecastMode.MOCK

    def postprocess(
        self, sample_paths: np.ndarray, ctx: ModelContext, *, symbol: str, timeframe: str,
        mode: ForecastMode
    ) -> ForecastDistribution:
        model_name = "mock-gbm-v1" if mode == ForecastMode.MOCK else self.config.model_name
        return build_distribution(
            sample_paths=sample_paths,
            last_close=ctx.last_close,
            realized_volatility=ctx.realized_volatility,
            symbol=symbol,
            timeframe=timeframe,
            context_start=ctx.context_start,
            context_end=ctx.context_end,
            created_at=now_utc(),
            horizon=ctx.horizon,
            mode=mode,
            model_name=model_name,
            model_config_hash=self.config.config_hash(),
        )

    # --- convenience: full pipeline ----------------------------------------
    def forecast(self, df: pd.DataFrame, *, symbol: str, timeframe: str) -> ForecastDistribution:
        ctx = self.prepare_context(df, timeframe=timeframe)
        sample_paths, mode = self.predict(ctx, symbol)
        return self.postprocess(sample_paths, ctx, symbol=symbol, timeframe=timeframe, mode=mode)


def get_adapter(config: KronosConfig | None = None) -> KronosAdapter:
    return KronosAdapter(config or get_config_store().kronos())
