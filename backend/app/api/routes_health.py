"""Health + system status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_config_store, get_settings
from app.core.timeframes import now_utc
from app.db.session import get_db
from app.kronos.loader import real_model_available

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    kronos = get_config_store().kronos()
    available, reason = real_model_available(kronos)
    return {
        "status": "ok" if db_ok else "degraded",
        "time": now_utc().isoformat(),
        "env": settings.env,
        "database_ok": db_ok,
        "live_trading_enabled": settings.enable_live_trading,
        "scheduler_enabled": settings.enable_scheduler,
        "kronos": {
            "configured_model": kronos.model_name,
            "mock_mode_setting": kronos.mock_mode,
            "real_model_available": available,
            "real_model_reason": reason,
            "effective_mode": "mock" if (not available or str(kronos.mock_mode).lower() == "true") else "real",
        },
    }
