"""Signal + regime snapshot persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RegimeSnapshot, Signal, SignalExplanation


def save_regime_snapshot(db: Session, snapshot: dict) -> RegimeSnapshot:
    row = RegimeSnapshot(
        symbol=snapshot["symbol"],
        timeframe=snapshot["timeframe"],
        as_of=snapshot["as_of"],
        regime=snapshot["regime"],
        regime_score=snapshot["regime_score"],
        market_regime=snapshot.get("market_regime"),
        features=snapshot.get("features", {}),
        explanation=snapshot.get("explanation", ""),
    )
    db.add(row)
    db.flush()
    return row


def save_signal(db: Session, signal: dict, explanations: list[dict] | None = None) -> Signal:
    row = Signal(
        symbol=signal["symbol"],
        timeframe=signal["timeframe"],
        as_of=signal["as_of"],
        forecast_run_id=signal.get("forecast_run_id"),
        regime_snapshot_id=signal.get("regime_snapshot_id"),
        side=signal.get("side"),
        status=signal["status"],
        confidence_label=signal.get("confidence_label", "none"),
        p_up=signal["p_up"],
        p_down=signal["p_down"],
        median_return=signal["median_return"],
        q10_return=signal["q10_return"],
        q90_return=signal["q90_return"],
        asymmetry_score=signal["asymmetry_score"],
        forecast_volatility_ratio=signal["forecast_volatility_ratio"],
        path_quality=signal["path_quality"],
        trend_alignment=signal["trend_alignment"],
        regime_score=signal["regime_score"],
        liquidity_score=signal["liquidity_score"],
        cost_adjusted_edge=signal["cost_adjusted_edge"],
        edge_score=signal["edge_score"],
        entry_zone_low=signal.get("entry_zone_low"),
        entry_zone_high=signal.get("entry_zone_high"),
        invalidation_level=signal.get("invalidation_level"),
        reason_codes=signal.get("reason_codes", []),
        edge_formula_version=signal.get("edge_formula_version", "v1"),
    )
    db.add(row)
    db.flush()

    for exp in explanations or []:
        db.add(
            SignalExplanation(
                signal_id=row.id,
                factor=exp["factor"],
                value=exp.get("value"),
                threshold=exp.get("threshold"),
                passed=exp.get("passed", False),
                text=exp.get("text", ""),
            )
        )
    db.flush()
    return row


def latest_signals(db: Session, timeframe: str | None = None, limit: int = 100) -> list[Signal]:
    """Most recent signal per symbol, ranked by edge_score desc."""
    stmt = select(Signal).order_by(Signal.as_of.desc(), Signal.edge_score.desc())
    if timeframe:
        stmt = stmt.where(Signal.timeframe == timeframe)
    rows = list(db.execute(stmt.limit(limit * 4)).scalars().all())

    seen: set[str] = set()
    latest: list[Signal] = []
    for r in rows:
        if r.symbol in seen:
            continue
        seen.add(r.symbol)
        latest.append(r)
    latest.sort(key=lambda s: s.edge_score, reverse=True)
    return latest[:limit]


def latest_regime(db: Session, symbol: str, timeframe: str) -> RegimeSnapshot | None:
    stmt = (
        select(RegimeSnapshot)
        .where(RegimeSnapshot.symbol == symbol, RegimeSnapshot.timeframe == timeframe)
        .order_by(RegimeSnapshot.as_of.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def signals_since(db: Session, since: datetime, timeframe: str | None = None) -> list[Signal]:
    stmt = select(Signal).where(Signal.as_of >= since)
    if timeframe:
        stmt = stmt.where(Signal.timeframe == timeframe)
    return list(db.execute(stmt.order_by(Signal.edge_score.desc())).scalars().all())
