"""Signal endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import signals_repo
from app.scheduler import jobs

router = APIRouter(tags=["signals"])


class SignalsRunRequest(BaseModel):
    timeframe: str | None = None


@router.post("/signals/run")
def run_signals(req: SignalsRunRequest, db: Session = Depends(get_db)) -> dict:
    rows = jobs.run_signals(db, timeframe=req.timeframe)
    return {"count": len(rows), "signals": [_signal_dict(s) for s in rows]}


@router.get("/signals/latest")
def latest_signals(timeframe: str | None = None, limit: int = 100, db: Session = Depends(get_db)) -> dict:
    rows = signals_repo.latest_signals(db, timeframe=timeframe, limit=limit)
    return {"count": len(rows), "signals": [_signal_dict(s) for s in rows]}


def _signal_dict(s) -> dict:
    return {
        "id": s.id,
        "symbol": s.symbol,
        "timeframe": s.timeframe,
        "as_of": s.as_of.isoformat() if s.as_of else None,
        "side": s.side,
        "status": s.status,
        "confidence_label": s.confidence_label,
        "p_up": s.p_up,
        "p_down": s.p_down,
        "median_return": s.median_return,
        "q10_return": s.q10_return,
        "q90_return": s.q90_return,
        "asymmetry_score": s.asymmetry_score,
        "forecast_volatility_ratio": s.forecast_volatility_ratio,
        "path_quality": s.path_quality,
        "trend_alignment": s.trend_alignment,
        "regime_score": s.regime_score,
        "liquidity_score": s.liquidity_score,
        "cost_adjusted_edge": s.cost_adjusted_edge,
        "edge_score": s.edge_score,
        "entry_zone_low": float(s.entry_zone_low) if s.entry_zone_low is not None else None,
        "entry_zone_high": float(s.entry_zone_high) if s.entry_zone_high is not None else None,
        "invalidation_level": float(s.invalidation_level) if s.invalidation_level is not None else None,
        "reason_codes": s.reason_codes,
        "edge_formula_version": s.edge_formula_version,
        "forecast_run_id": s.forecast_run_id,
    }
