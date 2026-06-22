"""APScheduler runner. Disabled unless KAT_ENABLE_SCHEDULER=true.

Records every run in scheduler_runs so the dashboard can show scheduler health.
Each job opens its own DB session and is wrapped so one failure never kills the
scheduler thread.
"""

from __future__ import annotations

from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.db.models import SchedulerRun
from app.db.session import new_session
from app.logging_config import get_logger
from app.scheduler import jobs

log = get_logger("scheduler.runner")

_scheduler: BackgroundScheduler | None = None


def _run_job(job_name: str, fn) -> None:
    db = new_session()
    run = SchedulerRun(job_name=job_name, status="running")
    db.add(run)
    db.commit()
    try:
        detail = fn(db)
        run.status = "done"
        run.detail = detail if isinstance(detail, dict) else {"result": str(detail)}
    except Exception as exc:  # never let a job crash the scheduler
        db.rollback()
        run.status = "error"
        run.error = str(exc)
        log.error("scheduler_job_failed", job=job_name, error=str(exc))
    finally:
        run.finished_at = datetime.now(tz=timezone.utc)
        db.add(run)
        db.commit()
        db.close()


def _ingest_then_signals(db) -> dict:
    ingest = jobs.run_ingest(db)
    db.commit()
    signals = jobs.run_signals(db)
    return {"ingest": ingest, "signals": len(signals)}


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    settings = get_settings()
    if not settings.enable_scheduler:
        log.info("scheduler_disabled")
        return None
    if _scheduler is not None:
        return _scheduler

    sched = BackgroundScheduler(timezone="UTC")
    # Hourly: ingest fresh candles then recompute signals.
    sched.add_job(
        lambda: _run_job("ingest_signals", _ingest_then_signals),
        "interval", minutes=60, id="ingest_signals", max_instances=1, coalesce=True,
    )
    # Every 30 seconds: ingest fresh candles to keep close prices updated in real-time.
    sched.add_job(
        lambda: _run_job("fast_ingest", lambda db: jobs.run_ingest(db, lookback_candles=5)),
        "interval", seconds=30, id="fast_ingest", max_instances=1, coalesce=True,
    )
    # Every 1 minute: fast rescore of existing forecasts using the newest candles.
    sched.add_job(
        lambda: _run_job("fast_rescore", jobs.run_fast_rescore),
        "interval", minutes=1, id="fast_rescore", max_instances=1, coalesce=True,
    )
    # Every 10 seconds: manage open paper orders (stop/take-profit checks).
    sched.add_job(
        lambda: _run_job("manage_paper", jobs.manage_paper),
        "interval", seconds=10, id="manage_paper", max_instances=1, coalesce=True,
    )
    sched.start()
    _scheduler = sched
    log.info("scheduler_started")
    return sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
