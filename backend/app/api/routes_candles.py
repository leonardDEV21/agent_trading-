"""Candle ingestion + retrieval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_config_store
from app.data.ingestion.candle_ingestor import ingest_candles
from app.db.session import get_db
from app.repositories import candles_repo

router = APIRouter(tags=["candles"])


class IngestRequest(BaseModel):
    symbol: str
    exchange: str = "binance"
    asset_type: str = "crypto"
    timeframe: str = "1h"
    lookback_candles: int = 1000


@router.post("/ingest/candles")
def ingest(req: IngestRequest, db: Session = Depends(get_db)) -> dict:
    res = ingest_candles(
        db, symbol=req.symbol, exchange=req.exchange, asset_type=req.asset_type,
        timeframe=req.timeframe, lookback_candles=req.lookback_candles,
    )
    return {
        "symbol": res.symbol, "exchange": res.exchange, "timeframe": res.timeframe,
        "fetched": res.fetched, "inserted": res.inserted, "duplicates": res.duplicates,
        "invalid": res.invalid, "gaps_found": res.gaps_found, "issues": res.issues[:10],
    }


@router.get("/candles")
def get_candles(
    symbol: str,
    timeframe: str = "1h",
    limit: int = Query(500, le=5000),
    db: Session = Depends(get_db),
) -> dict:
    rows = candles_repo.get_candles(db, symbol, timeframe, ascending=False, limit=limit)
    rows.reverse()
    candles = [
        {
            "timestamp_open": c.timestamp_open.isoformat(),
            "open": float(c.open), "high": float(c.high), "low": float(c.low),
            "close": float(c.close), "volume": float(c.volume),
        }
        for c in rows
    ]
    return {"symbol": symbol, "timeframe": timeframe, "count": len(candles), "candles": candles}
