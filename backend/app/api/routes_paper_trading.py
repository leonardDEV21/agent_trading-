"""Paper trading endpoints. Paper only — never sends real orders."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_config_store
from app.core.constants import Side
from app.db.session import get_db
from app.paper import ledger
from app.repositories import paper_trades_repo

router = APIRouter(tags=["paper"])


class PaperOrderRequest(BaseModel):
    symbol: str
    side: Side
    timeframe: str | None = None
    signal_id: int | None = None
    forecast_id: int | None = None
    thesis: str = ""


from app.repositories import candles_repo

@router.get("/paper/orders")
def list_orders(status: str | None = None, db: Session = Depends(get_db)) -> dict:
    rows = paper_trades_repo.list_orders(db, status=status)
    orders_dict = []
    default_timeframe = ledger._default_timeframe()
    for o in rows:
        d = ledger._order_to_dict(o)
        if o.status == "open":
            latest = candles_repo.get_latest_candle(db, o.symbol, default_timeframe)
            if latest:
                cur_price = float(latest.close)
                d["current_price"] = cur_price
                side_factor = 1 if o.side == "long" else -1
                d["unrealized_pnl"] = (cur_price - float(o.entry_price)) * float(o.size) * side_factor
            else:
                d["current_price"] = None
                d["unrealized_pnl"] = 0.0
        else:
            d["current_price"] = None
            d["unrealized_pnl"] = 0.0
        orders_dict.append(d)
    return {"count": len(rows), "orders": orders_dict}


@router.post("/paper/orders", status_code=201)
def create_order(req: PaperOrderRequest, db: Session = Depends(get_db)) -> dict:
    risk = get_config_store().risk()
    return ledger.open_paper_order(
        db, symbol=req.symbol, side=req.side, risk=risk, timeframe=req.timeframe,
        signal_id=req.signal_id, forecast_id=req.forecast_id, thesis=req.thesis,
    )


class CloseRequest(BaseModel):
    exit_price: float | None = None
    reason: str = "manual"


@router.post("/paper/orders/{order_id}/close")
def close_order(order_id: str, req: CloseRequest, db: Session = Depends(get_db)) -> dict:
    risk = get_config_store().risk()
    return ledger.close_paper_order(
        db, order_id, risk=risk, exit_price=req.exit_price, reason=req.reason
    )


@router.post("/paper/reset")
def reset_paper(db: Session = Depends(get_db)) -> dict:
    deleted = paper_trades_repo.reset_paper(db)
    return {"deleted": deleted}
