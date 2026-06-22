"""Paper trading ledger — the only way paper orders are created/closed.

Always routes through the risk engine (assess_trade) so a paper order can never
violate the same limits a live order would face. Live execution is NOT here; it
lives behind a separate, disabled adapter.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import RiskConfig, get_config_store
from app.core.constants import OrderStatus, ReasonCode, Side
from app.core.errors import NotFoundError, RiskBlockedError
from app.core.timeframes import now_utc
from app.db.models import Signal
from app.logging_config import get_logger
from app.paper import portfolio
from app.paper.order_simulator import simulate_fill
from app.repositories import candles_repo, paper_trades_repo
from app.repositories import signals_repo
from app.risk import kill_switch
from app.risk.exposure_limits import assess_trade
from app.strategy import volatility_engine as ind

log = get_logger("paper.ledger")


def _default_timeframe() -> str:
    return get_config_store().timeframes().get("default", "1h")


def open_paper_order(
    db: Session,
    *,
    symbol: str,
    side: Side,
    risk: RiskConfig,
    timeframe: str | None = None,
    signal_id: int | None = None,
    forecast_id: int | None = None,
    thesis: str = "",
) -> dict:
    """Create a paper order from a candidate, sized + gated by the risk engine."""
    timeframe = timeframe or _default_timeframe()
    candles = candles_repo.get_candles(db, symbol, timeframe, ascending=False, limit=400)
    if len(candles) < 50:
        raise NotFoundError(f"Not enough candle history for {symbol} to open a paper order")
    df = candles_repo.candles_to_df(candles)

    entry_ref = float(df["close"].iloc[-1])
    atr_val = float(ind.atr(df).iloc[-1])

    invalidation = None
    forecast_target = None
    if signal_id is not None:
        sig = db.get(Signal, signal_id)
        if sig is not None:
            invalidation = float(sig.invalidation_level) if sig.invalidation_level else None
            forecast_target = None

    beta = {a.symbol: a.beta_group for a in get_config_store().all_assets()}.get(symbol)
    ks_state = kill_switch.get_state(db)
    summary = portfolio.portfolio_summary(db, risk)

    decision = assess_trade(
        side=side, entry=entry_ref, atr=atr_val, invalidation_level=invalidation,
        forecast_target=forecast_target, beta_group=beta,
        open_positions=portfolio.open_position_views(db),
        daily_pnl_pct=summary["daily_pnl_pct"], kill_switch_active=ks_state.active, risk=risk,
    )
    if not decision.allowed:
        raise RiskBlockedError(
            "Risk engine blocked this paper order", detail={"reason_codes": decision.reason_codes}
        )

    fill = simulate_fill(
        side=side, reference_price=entry_ref, size=decision.size,
        fee_bps=risk.fee_bps, slippage_bps=risk.slippage_bps, atr=atr_val,
    )

    order = {
        "paper_order_id": uuid.uuid4().hex[:16],
        "symbol": symbol,
        "side": side.value,
        "entry_time": now_utc(),
        "entry_price": fill.fill_price,
        "stop_loss": decision.stop,
        "take_profit": decision.take_profit,
        "size": decision.size,
        "risk_amount": decision.risk_amount,
        "thesis": thesis,
        "forecast_id": forecast_id,
        "signal_id": signal_id,
        "status": OrderStatus.OPEN.value,
        "fees": fill.fee,
        "slippage": fill.slippage,
    }
    row = paper_trades_repo.create_order(db, order)
    log.info("paper_order_opened", paper_order_id=row.paper_order_id, symbol=symbol, side=side.value)
    return _order_to_dict(row)


def close_paper_order(
    db: Session, paper_order_id: str, *, risk: RiskConfig, exit_price: float | None = None,
    reason: str = "manual", timeframe: str | None = None,
) -> dict:
    order = paper_trades_repo.get_order(db, paper_order_id)
    if order is None:
        raise NotFoundError(f"Paper order {paper_order_id} not found")
    if order.status != OrderStatus.OPEN.value:
        raise RiskBlockedError(f"Paper order {paper_order_id} is not open")

    timeframe = timeframe or _default_timeframe()
    if exit_price is None:
        latest = candles_repo.get_latest_candle(db, order.symbol, timeframe)
        exit_price = float(latest.close) if latest else float(order.entry_price)

    side = Side(order.side)
    exit_side = Side.SHORT if side == Side.LONG else Side.LONG
    fill = simulate_fill(
        side=exit_side, reference_price=exit_price, size=float(order.size),
        fee_bps=risk.fee_bps, slippage_bps=risk.slippage_bps,
    )
    direction = 1 if side == Side.LONG else -1
    gross = (fill.fill_price - float(order.entry_price)) * float(order.size) * direction
    total_fees = float(order.fees or 0.0) + fill.fee
    net = gross - fill.fee  # entry fee already deducted conceptually; keep symmetric
    net = gross - total_fees

    paper_trades_repo.close_order(
        db, order, exit_time=now_utc(), exit_price=fill.fill_price, realized_pnl=round(net, 6),
        fees=round(total_fees, 6), slippage=round(float(order.slippage or 0.0) + fill.slippage, 6),
        exit_reason=reason,
    )
    log.info("paper_order_closed", paper_order_id=paper_order_id, net_pnl=round(net, 2), reason=reason)
    return _order_to_dict(order)


def auto_manage_open_orders(db: Session, *, risk: RiskConfig, timeframe: str | None = None) -> int:
    """Check open paper orders against the latest candle; close on stop/tp. Returns count closed."""
    timeframe = timeframe or _default_timeframe()
    closed = 0
    for order in paper_trades_repo.open_orders(db):
        latest = candles_repo.get_latest_candle(db, order.symbol, timeframe)
        if latest is None:
            continue
        side = Side(order.side)
        high, low = float(latest.high), float(latest.low)
        reason = None
        price = None
        if side == Side.LONG:
            if low <= float(order.stop_loss):
                price, reason = float(order.stop_loss), ReasonCode.EXIT_STOP_LOSS.value
            elif order.take_profit and high >= float(order.take_profit):
                price, reason = float(order.take_profit), ReasonCode.EXIT_TAKE_PROFIT.value
        else:
            if high >= float(order.stop_loss):
                price, reason = float(order.stop_loss), ReasonCode.EXIT_STOP_LOSS.value
            elif order.take_profit and low <= float(order.take_profit):
                price, reason = float(order.take_profit), ReasonCode.EXIT_TAKE_PROFIT.value
        if price is not None:
            close_paper_order(db, order.paper_order_id, risk=risk, exit_price=price, reason=reason)
            closed += 1
    return closed


def _order_to_dict(o) -> dict:
    return {
        "paper_order_id": o.paper_order_id,
        "symbol": o.symbol,
        "side": o.side,
        "entry_time": o.entry_time,
        "entry_price": float(o.entry_price),
        "stop_loss": float(o.stop_loss),
        "take_profit": float(o.take_profit) if o.take_profit is not None else None,
        "size": float(o.size),
        "risk_amount": o.risk_amount,
        "thesis": o.thesis,
        "forecast_id": o.forecast_id,
        "signal_id": o.signal_id,
        "status": o.status,
        "exit_time": o.exit_time,
        "exit_price": float(o.exit_price) if o.exit_price is not None else None,
        "realized_pnl": o.realized_pnl,
        "fees": o.fees,
        "slippage": o.slippage,
        "exit_reason": o.exit_reason,
    }
