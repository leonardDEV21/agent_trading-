"""Forecast run persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ForecastPath, ForecastRun


def save_forecast(db: Session, forecast: dict) -> ForecastRun:
    """Persist a forecast distribution produced by the Kronos adapter.

    ``forecast`` is the dict returned by ForecastDistribution.to_dict().
    """
    run = ForecastRun(
        symbol=forecast["symbol"],
        timeframe=forecast["timeframe"],
        context_start=forecast["context_start"],
        context_end=forecast["context_end"],
        horizon=forecast["horizon"],
        sample_count=forecast["sample_count"],
        mode=forecast["mode"],
        model_name=forecast["model_name"],
        model_config_hash=forecast["model_config_hash"],
        last_close=forecast["last_close"],
        p_up=forecast["p_up"],
        p_down=forecast["p_down"],
        median_return=forecast["median_return"],
        q10_return=forecast["q10_return"],
        q25_return=forecast["q25_return"],
        q75_return=forecast["q75_return"],
        q90_return=forecast["q90_return"],
        forecast_volatility=forecast["forecast_volatility"],
        forecast_volatility_ratio=forecast["forecast_volatility_ratio"],
    )
    db.add(run)
    db.flush()  # assign run.id

    quantile_paths = {
        "median": forecast["median_path"],
        "q10": forecast["q10_path"],
        "q25": forecast["q25_path"],
        "q75": forecast["q75_path"],
        "q90": forecast["q90_path"],
    }
    for ptype, values in quantile_paths.items():
        db.add(ForecastPath(forecast_run_id=run.id, path_type=ptype, values=values))

    # Optionally persist a capped number of raw sample paths for the fan chart.
    for i, path in enumerate(forecast.get("forecast_paths", [])[:50]):
        db.add(
            ForecastPath(
                forecast_run_id=run.id, path_type="sample", sample_index=i, values=path
            )
        )
    db.flush()
    return run


def get_forecast(db: Session, forecast_id: int) -> ForecastRun | None:
    return db.get(ForecastRun, forecast_id)


def get_cached_forecast(
    db: Session,
    symbol: str,
    timeframe: str,
    context_end: datetime,
    model_config_hash: str,
) -> ForecastRun | None:
    """Look up an existing forecast for an exact context end + config.

    Used by the backtester to avoid recomputing forecasts. The context_end must
    match exactly so we never reuse a forecast that "saw" future candles.
    """
    stmt = (
        select(ForecastRun)
        .where(
            ForecastRun.symbol == symbol,
            ForecastRun.timeframe == timeframe,
            ForecastRun.context_end == context_end,
            ForecastRun.model_config_hash == model_config_hash,
        )
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def get_paths(db: Session, forecast_id: int) -> list[ForecastPath]:
    stmt = select(ForecastPath).where(ForecastPath.forecast_run_id == forecast_id)
    return list(db.execute(stmt).scalars().all())


def get_latest_forecast(db: Session, symbol: str, timeframe: str) -> ForecastRun | None:
    """Look up the most recent forecast run for a symbol."""
    stmt = (
        select(ForecastRun)
        .where(ForecastRun.symbol == symbol, ForecastRun.timeframe == timeframe)
        .order_by(ForecastRun.context_end.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def reconstruct_forecast_distribution(db: Session, run: ForecastRun):
    """Reconstruct a ForecastDistribution from a persisted ForecastRun."""
    import numpy as np
    from app.core.constants import ForecastMode
    from app.kronos.forecast_postprocessor import ForecastDistribution

    paths = get_paths(db, run.id)
    median_path = next((p.values for p in paths if p.path_type == "median"), [])
    q10_path = next((p.values for p in paths if p.path_type == "q10"), [])
    q25_path = next((p.values for p in paths if p.path_type == "q25"), [])
    q75_path = next((p.values for p in paths if p.path_type == "q75"), [])
    q90_path = next((p.values for p in paths if p.path_type == "q90"), [])
    forecast_paths = [p.values for p in paths if p.path_type == "sample"]

    eps = 1e-8
    if forecast_paths:
        terminal_returns = np.array([p[-1] / float(run.last_close) - 1.0 for p in forecast_paths])
        std_terminal = float(np.std(terminal_returns))
    else:
        # fallback using quantiles if raw paths are missing
        std_terminal = (run.q90_return - run.q10_return) / 2.563

    uncertainty_score = float(
        np.clip(std_terminal / (abs(run.median_return) + std_terminal + eps), 0.0, 1.0)
    )

    return ForecastDistribution(
        symbol=run.symbol,
        timeframe=run.timeframe,
        created_at=run.created_at,
        context_start=run.context_start,
        context_end=run.context_end,
        horizon=run.horizon,
        sample_count=run.sample_count,
        mode=ForecastMode(run.mode),
        model_name=run.model_name,
        model_config_hash=run.model_config_hash,
        last_close=float(run.last_close),
        median_path=median_path,
        q10_path=q10_path,
        q25_path=q25_path,
        q75_path=q75_path,
        q90_path=q90_path,
        forecast_paths=forecast_paths,
        p_up=run.p_up,
        p_down=run.p_down,
        median_return=run.median_return,
        q10_return=run.q10_return,
        q25_return=run.q25_return,
        q75_return=run.q75_return,
        q90_return=run.q90_return,
        forecast_volatility=run.forecast_volatility,
        forecast_volatility_ratio=run.forecast_volatility_ratio,
        uncertainty_score=uncertainty_score,
    )
