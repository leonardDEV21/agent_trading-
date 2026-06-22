"""Paper order persistence and open-position aggregation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import OrderStatus
from app.core.symbols import normalize_symbol
from app.db.models import PaperOrder


def create_order(db: Session, order: dict) -> PaperOrder:
    row = PaperOrder(**order)
    db.add(row)
    db.flush()
    return row


def get_order(db: Session, paper_order_id: str) -> PaperOrder | None:
    stmt = select(PaperOrder).where(PaperOrder.paper_order_id == paper_order_id)
    return db.execute(stmt).scalars().first()


def list_orders(db: Session, status: str | None = None, limit: int = 200) -> list[PaperOrder]:
    stmt = select(PaperOrder).order_by(PaperOrder.entry_time.desc())
    if status:
        stmt = stmt.where(PaperOrder.status == status)
    return list(db.execute(stmt.limit(limit)).scalars().all())


def open_orders(db: Session) -> list[PaperOrder]:
    return list_orders(db, status=OrderStatus.OPEN.value)


def open_orders_for_symbol(db: Session, symbol: str) -> list[PaperOrder]:
    symbol = normalize_symbol(symbol)
    stmt = select(PaperOrder).where(
        PaperOrder.symbol == symbol, PaperOrder.status == OrderStatus.OPEN.value
    )
    return list(db.execute(stmt).scalars().all())


def close_order(db: Session, order: PaperOrder, *, exit_time, exit_price, realized_pnl,
                fees, slippage, exit_reason) -> PaperOrder:
    order.status = OrderStatus.CLOSED.value
    order.exit_time = exit_time
    order.exit_price = exit_price
    order.realized_pnl = realized_pnl
    order.fees = fees
    order.slippage = slippage
    order.exit_reason = exit_reason
    db.flush()
    return order


def reset_paper(db: Session) -> int:
    """Delete all paper orders (make paper_reset). Returns rows deleted."""
    rows = db.query(PaperOrder).delete()
    db.flush()
    return rows
