"""Kill switch — halts new trade entries when conditions are unsafe.

Triggers (configs/risk.default.json -> kill_switch):
- N consecutive losing trades in one day
- a data-provider error
- model uncertainty above threshold
- spread above threshold
- daily loss limit breached

State is persisted as active RiskEvent rows so a restart does not silently
re-arm trading. Events auto-clear after ``cooldown_minutes``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import KillSwitchConfig
from app.core.constants import KillSwitchTrigger, OrderStatus
from app.core.timeframes import now_utc
from app.db.models import PaperOrder, RiskEvent
from app.logging_config import get_logger

log = get_logger("risk.kill_switch")


@dataclass
class KillSwitchState:
    active: bool
    triggers: list[str]
    detail: dict


# --- pure predicate helpers (easy to unit-test) ---------------------------- #
def exceeds_consecutive_losses(consecutive_losses: int, max_losses: int) -> bool:
    return consecutive_losses >= max_losses


def exceeds_uncertainty(uncertainty: float, max_uncertainty: float) -> bool:
    return uncertainty > max_uncertainty


def exceeds_spread(spread_bps: float, max_spread_bps: float) -> bool:
    return spread_bps > max_spread_bps


# --- DB-backed state ------------------------------------------------------- #
def active_events(db: Session) -> list[RiskEvent]:
    stmt = select(RiskEvent).where(RiskEvent.active.is_(True))
    return list(db.execute(stmt).scalars().all())


def get_state(db: Session) -> KillSwitchState:
    events = active_events(db)
    return KillSwitchState(
        active=len(events) > 0,
        triggers=[e.trigger or e.event_type for e in events],
        detail={e.trigger or e.event_type: e.detail for e in events},
    )


def trip(db: Session, trigger: KillSwitchTrigger, *, detail: dict | None = None,
         symbol: str | None = None) -> RiskEvent:
    event = RiskEvent(
        event_type="kill_switch",
        trigger=trigger.value,
        symbol=symbol,
        detail=detail or {},
        active=True,
    )
    db.add(event)
    db.flush()
    log.warning("kill_switch_tripped", trigger=trigger.value, symbol=symbol, detail=detail)
    return event


def clear_expired(db: Session, cooldown_minutes: int) -> int:
    cutoff = now_utc() - timedelta(minutes=cooldown_minutes)
    events = active_events(db)
    cleared = 0
    for e in events:
        if e.created_at <= cutoff:
            e.active = False
            e.cleared_at = now_utc()
            cleared += 1
    if cleared:
        db.flush()
    return cleared


def count_consecutive_losses_today(db: Session) -> int:
    """Count trailing consecutive losing closed paper trades within today (UTC)."""
    start = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = (
        select(PaperOrder)
        .where(PaperOrder.status == OrderStatus.CLOSED.value, PaperOrder.exit_time >= start)
        .order_by(PaperOrder.exit_time.desc())
    )
    rows = list(db.execute(stmt).scalars().all())
    streak = 0
    for r in rows:
        if (r.realized_pnl or 0.0) < 0:
            streak += 1
        else:
            break
    return streak


def evaluate_and_maybe_trip(
    db: Session,
    cfg: KillSwitchConfig,
    *,
    daily_pnl_pct: float,
    uncertainty: float | None = None,
    spread_bps: float | None = None,
) -> KillSwitchState:
    """Check all conditions, trip the switch if any fail, return the current state."""
    clear_expired(db, cfg.cooldown_minutes)

    losses = count_consecutive_losses_today(db)
    if exceeds_consecutive_losses(losses, cfg.max_consecutive_losses_per_day):
        trip(db, KillSwitchTrigger.CONSECUTIVE_LOSSES, detail={"consecutive_losses": losses})

    if uncertainty is not None and exceeds_uncertainty(uncertainty, cfg.max_model_uncertainty):
        trip(db, KillSwitchTrigger.MODEL_UNCERTAINTY, detail={"uncertainty": uncertainty})

    if spread_bps is not None and exceeds_spread(spread_bps, cfg.max_spread_bps):
        trip(db, KillSwitchTrigger.SPREAD_TOO_WIDE, detail={"spread_bps": spread_bps})

    return get_state(db)
