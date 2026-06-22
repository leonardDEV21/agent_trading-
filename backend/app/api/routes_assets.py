"""Asset universe endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_config_store
from app.data.contracts.asset_schema import AssetIn
from app.db.models import Asset
from app.db.session import get_db

router = APIRouter(tags=["assets"])


@router.get("/assets")
def list_assets(db: Session = Depends(get_db)) -> dict:
    """Config-defined universe merged with any DB-registered assets."""
    config_assets = [a.model_dump() for a in get_config_store().all_assets()]
    db_assets = [
        {
            "symbol": a.symbol, "exchange": a.exchange, "asset_type": a.asset_type,
            "display_name": a.display_name, "is_market_benchmark": a.is_market_benchmark,
            "beta_group": a.beta_group, "min_notional_usd": a.min_notional_usd, "enabled": a.enabled,
            "id": a.id,
        }
        for a in db.execute(select(Asset)).scalars().all()
    ]
    known = {a["symbol"] for a in config_assets}
    merged = config_assets + [a for a in db_assets if a["symbol"] not in known]
    return {"assets": merged, "count": len(merged)}


@router.post("/assets", status_code=201)
def create_asset(payload: AssetIn, db: Session = Depends(get_db)) -> dict:
    existing = db.execute(
        select(Asset).where(Asset.symbol == payload.symbol, Asset.exchange == payload.exchange)
    ).scalars().first()
    if existing:
        for k, v in payload.model_dump().items():
            setattr(existing, k, v)
        db.flush()
        row = existing
    else:
        row = Asset(**payload.model_dump())
        db.add(row)
        db.flush()
    return {"id": row.id, "symbol": row.symbol, "exchange": row.exchange}
