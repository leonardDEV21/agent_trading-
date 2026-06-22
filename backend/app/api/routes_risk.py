"""Risk status endpoint: kill switch + portfolio + limits."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_config_store
from app.db.session import get_db
from app.paper import portfolio
from app.risk import kill_switch

router = APIRouter(tags=["risk"])


@router.get("/risk/status")
def risk_status(db: Session = Depends(get_db)) -> dict:
    risk = get_config_store().risk()
    state = kill_switch.get_state(db)
    summary = portfolio.portfolio_summary(db, risk)
    return {
        "kill_switch_active": state.active,
        "kill_switch_triggers": state.triggers,
        "kill_switch_detail": state.detail,
        "limits": {
            "risk_per_trade": risk.risk_per_trade,
            "max_daily_loss": risk.max_daily_loss,
            "max_open_positions": risk.max_open_positions,
            "max_correlated_positions": risk.max_correlated_positions,
            "allow_leverage": risk.allow_leverage,
        },
        "portfolio": summary,
        "consecutive_losses_today": kill_switch.count_consecutive_losses_today(db),
    }
