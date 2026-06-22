"""Paper portfolio state: equity, open exposure, risk usage, daily PnL."""

from __future__ import annotations

from app.config import RiskConfig, get_config_store
from app.core.timeframes import now_utc, ensure_utc
from app.risk.exposure_limits import OpenPositionView
from app.repositories import paper_trades_repo as paper_repo
from sqlalchemy.orm import Session


def _beta_map() -> dict[str, str | None]:
    return {a.symbol: a.beta_group for a in get_config_store().all_assets()}


def open_position_views(db: Session) -> list[OpenPositionView]:
    beta = _beta_map()
    views = []
    for o in paper_repo.open_orders(db):
        views.append(OpenPositionView(symbol=o.symbol, beta_group=beta.get(o.symbol)))
    return views


def realized_equity(db: Session, account_size: float) -> float:
    closed = paper_repo.list_orders(db, status="closed", limit=100000)
    return account_size + sum((o.realized_pnl or 0.0) for o in closed)


def daily_realized_pnl(db: Session) -> float:
    start = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    closed = paper_repo.list_orders(db, status="closed", limit=100000)
    return sum((o.realized_pnl or 0.0) for o in closed if o.exit_time and ensure_utc(o.exit_time) >= start)


def open_risk_amount(db: Session) -> float:
    return sum((o.risk_amount or 0.0) for o in paper_repo.open_orders(db))


def portfolio_summary(db: Session, risk: RiskConfig) -> dict:
    open_orders = paper_repo.open_orders(db)
    equity = realized_equity(db, risk.account_size)
    day_pnl = daily_realized_pnl(db)
    risk_used = open_risk_amount(db)
    return {
        "account_size": risk.account_size,
        "realized_equity": round(equity, 2),
        "open_positions": len(open_orders),
        "max_open_positions": risk.max_open_positions,
        "open_risk_amount": round(risk_used, 2),
        "open_risk_pct": round(risk_used / risk.account_size, 4) if risk.account_size else 0.0,
        "daily_realized_pnl": round(day_pnl, 2),
        "daily_loss_limit": round(risk.account_size * risk.max_daily_loss, 2),
        "daily_pnl_pct": round(day_pnl / risk.account_size, 4) if risk.account_size else 0.0,
        "symbols_open": [o.symbol for o in open_orders],
    }
