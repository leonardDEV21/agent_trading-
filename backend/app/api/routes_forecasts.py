"""Forecast endpoints. Mock-mode output is always explicitly labeled."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.session import get_db
from app.repositories import forecasts_repo
from app.scheduler import jobs

router = APIRouter(tags=["forecasts"])


class ForecastRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"


@router.post("/forecasts/run")
def run_forecast(req: ForecastRequest, db: Session = Depends(get_db)) -> dict:
    run = jobs.forecast_symbol(db, req.symbol, req.timeframe)
    return _summary(run)


@router.get("/forecasts/latest/{symbol:path}")
def get_latest_forecast(symbol: str, timeframe: str = "1h", db: Session = Depends(get_db)) -> dict:
    from sqlalchemy import desc, select
    from app.db.models import ForecastRun
    
    stmt = (
        select(ForecastRun)
        .where(ForecastRun.symbol == symbol, ForecastRun.timeframe == timeframe)
        .order_by(desc(ForecastRun.created_at))
        .limit(1)
    )
    run = db.execute(stmt).scalars().first()
    if run is None:
        return {"forecast": None}
    
    paths = forecasts_repo.get_paths(db, run.id)
    by_type: dict[str, list] = {}
    samples: list[list[float]] = []
    for p in paths:
        if p.path_type == "sample":
            samples.append(p.values)
        else:
            by_type[p.path_type] = p.values

    data = _summary(run)
    data.update(
        {
            "median_path": by_type.get("median", []),
            "q10_path": by_type.get("q10", []),
            "q25_path": by_type.get("q25", []),
            "q75_path": by_type.get("q75", []),
            "q90_path": by_type.get("q90", []),
            "sample_paths": samples,
        }
    )
    return {"forecast": data}


@router.get("/forecasts/{forecast_id}")
def get_forecast(forecast_id: int, db: Session = Depends(get_db)) -> dict:
    run = forecasts_repo.get_forecast(db, forecast_id)
    if run is None:
        raise NotFoundError(f"Forecast {forecast_id} not found")

    paths = forecasts_repo.get_paths(db, forecast_id)
    by_type: dict[str, list] = {}
    samples: list[list[float]] = []
    for p in paths:
        if p.path_type == "sample":
            samples.append(p.values)
        else:
            by_type[p.path_type] = p.values

    data = _summary(run)
    data.update(
        {
            "median_path": by_type.get("median", []),
            "q10_path": by_type.get("q10", []),
            "q25_path": by_type.get("q25", []),
            "q75_path": by_type.get("q75", []),
            "q90_path": by_type.get("q90", []),
            "sample_paths": samples,
        }
    )
    return data


def _summary(run) -> dict:
    return {
        "forecast_id": run.id,
        "symbol": run.symbol,
        "timeframe": run.timeframe,
        "created_at": run.created_at.isoformat(),
        "context_start": run.context_start.isoformat(),
        "context_end": run.context_end.isoformat(),
        "horizon": run.horizon,
        "sample_count": run.sample_count,
        "mode": run.mode,
        "is_mock": run.mode == "mock",
        "model_name": run.model_name,
        "model_config_hash": run.model_config_hash,
        "last_close": float(run.last_close),
        "p_up": run.p_up,
        "p_down": run.p_down,
        "median_return": run.median_return,
        "q10_return": run.q10_return,
        "q25_return": run.q25_return,
        "q75_return": run.q75_return,
        "q90_return": run.q90_return,
        "forecast_volatility": run.forecast_volatility,
        "forecast_volatility_ratio": run.forecast_volatility_ratio,
    }
