"""Backtest endpoints. Runs walk-forward synchronously (mock mode is fast)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.backtesting.walk_forward import run_walk_forward
from app.config import get_config_store
from app.core.errors import NotFoundError, ValidationError
from app.db.session import get_db
from app.kronos.adapter import KronosAdapter
from app.repositories import backtests_repo, candles_repo

router = APIRouter(tags=["backtests"])


class BacktestRequest(BaseModel):
    symbols: list[str] | None = None
    timeframe: str | None = None


@router.post("/backtests/run")
def run_backtest(req: BacktestRequest, db: Session = Depends(get_db)) -> dict:
    store = get_config_store()
    bt = store.backtest()
    strategy = store.strategy()
    risk = store.risk()
    kronos = store.kronos()

    symbols = req.symbols or bt.symbols
    timeframe = req.timeframe or bt.timeframe
    beta_groups = {a.symbol: a.beta_group for a in store.all_assets()}

    candles_by_symbol = {}
    for sym in symbols:
        rows = candles_repo.get_candles(db, sym, timeframe, ascending=True, limit=20000)
        if len(rows) < bt.warmup_candles + bt.test_window_candles:
            continue
        candles_by_symbol[sym] = candles_repo.candles_to_df(rows)

    if not candles_by_symbol:
        raise ValidationError(
            "No symbol has enough candle history. Ingest more candles first.",
            detail={"symbols": symbols, "needed": bt.warmup_candles + bt.test_window_candles},
        )

    adapter = KronosAdapter(kronos)
    result = run_walk_forward(
        candles_by_symbol, adapter=adapter, backtest=bt, strategy=strategy, risk=risk,
        kronos=kronos, beta_groups=beta_groups,
    )

    run = backtests_repo.create_run(
        db, symbols=list(candles_by_symbol.keys()), timeframe=timeframe,
        config_snapshot={"backtest": bt.model_dump(), "strategy": strategy.model_dump()},
        strategy_config_hash=str(strategy.edge_formula_version),
        kronos_config_hash=kronos.config_hash(), forecast_mode=result.forecast_mode,
    )

    for t in result.trades:
        backtests_repo.add_trade(db, run.id, t)

    peak = bt.initial_equity
    for ts, eq in result.equity_curve:
        peak = max(peak, eq)
        dd = (eq - peak) / peak if peak else 0.0
        backtests_repo.add_equity_point(db, run.id, ts, eq, round(dd, 6))

    backtests_repo.finalize_run(
        db, run, metrics=result.metrics, baseline_metrics=result.baseline_metrics
    )

    return {
        "backtest_id": run.id,
        "forecast_mode": result.forecast_mode,
        "metrics": result.metrics,
        "baseline_metrics": result.baseline_metrics,
        "num_trades": len(result.trades),
    }


@router.get("/backtests/{backtest_id}")
def get_backtest(backtest_id: int, db: Session = Depends(get_db)) -> dict:
    run = backtests_repo.get_run(db, backtest_id)
    if run is None:
        raise NotFoundError(f"Backtest {backtest_id} not found")
    return {
        "backtest_id": run.id,
        "status": run.status,
        "created_at": run.created_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "symbols": run.symbols,
        "timeframe": run.timeframe,
        "forecast_mode": run.forecast_mode,
        "metrics": run.metrics,
        "baseline_metrics": run.baseline_metrics,
        "config_snapshot": run.config_snapshot,
        "trades": [
            {
                "symbol": t.symbol, "side": t.side,
                "entry_time": t.entry_time.isoformat(), "entry_price": float(t.entry_price),
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "exit_price": float(t.exit_price) if t.exit_price is not None else None,
                "net_pnl": t.net_pnl, "fees": t.fees, "slippage": t.slippage,
                "regime": t.regime, "exit_reason": t.exit_reason,
            }
            for t in run.trades
        ],
        "equity_curve": [
            {"timestamp": e.timestamp.isoformat(), "equity": e.equity, "drawdown": e.drawdown}
            for e in sorted(run.equity_points, key=lambda x: x.timestamp)
        ],
    }
