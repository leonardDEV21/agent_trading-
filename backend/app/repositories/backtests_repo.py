"""Backtest run / trade / equity persistence."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import BacktestEquity, BacktestRun, BacktestTrade


def create_run(db: Session, *, symbols: list[str], timeframe: str, config_snapshot: dict,
               strategy_config_hash: str, kronos_config_hash: str, forecast_mode: str) -> BacktestRun:
    run = BacktestRun(
        status="running",
        symbols=symbols,
        timeframe=timeframe,
        config_snapshot=config_snapshot,
        strategy_config_hash=strategy_config_hash,
        kronos_config_hash=kronos_config_hash,
        forecast_mode=forecast_mode,
    )
    db.add(run)
    db.flush()
    return run


def add_trade(db: Session, run_id: int, trade: dict) -> BacktestTrade:
    row = BacktestTrade(backtest_run_id=run_id, **trade)
    db.add(row)
    return row


def add_equity_point(db: Session, run_id: int, timestamp: datetime, equity: float, drawdown: float) -> None:
    db.add(
        BacktestEquity(
            backtest_run_id=run_id, timestamp=timestamp, equity=equity, drawdown=drawdown
        )
    )


def finalize_run(db: Session, run: BacktestRun, *, metrics: dict, baseline_metrics: dict,
                 status: str = "done", error: str | None = None) -> BacktestRun:
    run.metrics = metrics
    run.baseline_metrics = baseline_metrics
    run.status = status
    run.error = error
    run.finished_at = datetime.now(tz=timezone.utc)
    db.flush()
    return run


def get_run(db: Session, run_id: int) -> BacktestRun | None:
    return db.get(BacktestRun, run_id)
