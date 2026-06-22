"""Reusable orchestration jobs shared by the scheduler, API routes and scripts.

Keeping the forecast/signal/ingest pipelines here (not in route handlers) means
the same code path runs whether triggered by cron, by an API call, or by a CLI
script — so behavior can't drift between them.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import KronosConfig, RiskConfig, StrategyConfig, get_config_store
from app.core.constants import Regime, TradeCandidateStatus, Side
from app.data.ingestion.candle_ingestor import ingest_candles
from app.db.models import ForecastRun, Signal
from app.kronos.adapter import KronosAdapter
from app.logging_config import get_logger
from app.paper import ledger
from app.repositories import candles_repo, forecasts_repo, signals_repo, paper_trades_repo
from app.strategy.regime_detector import detect_regime
from app.strategy.signal_scoring import score_signal

log = get_logger("scheduler.jobs")


# --------------------------------------------------------------------------- #
def run_ingest(db: Session, *, timeframe: str | None = None, lookback_candles: int = 1000) -> dict:
    store = get_config_store()
    timeframe = timeframe or store.timeframes().get("default", "1h")
    results = {}
    for asset in store.all_assets():
        if not asset.enabled:
            continue
        res = ingest_candles(
            db, symbol=asset.symbol, exchange=asset.exchange, asset_type=asset.asset_type,
            timeframe=timeframe, lookback_candles=lookback_candles,
        )
        results[asset.symbol] = {"inserted": res.inserted, "gaps": res.gaps_found}
    return results


def forecast_symbol(
    db: Session, symbol: str, timeframe: str, *, kronos: KronosConfig | None = None
) -> ForecastRun:
    kronos = kronos or get_config_store().kronos()
    candles = candles_repo.get_candles(
        db, symbol, timeframe, ascending=False, limit=kronos.context_length + 10
    )
    df = candles_repo.candles_to_df(candles)
    adapter = KronosAdapter(kronos)
    dist = adapter.forecast(df, symbol=symbol, timeframe=timeframe)
    run = forecasts_repo.save_forecast(db, dist.to_dict())
    log.info("forecast_saved", symbol=symbol, mode=dist.mode.value, forecast_id=run.id)
    return run


def _market_regime(db: Session, asset_type: str, timeframe: str, kronos: KronosConfig) -> Regime | None:
    store = get_config_store()
    benchmark = next(
        (a for a in store.all_assets() if a.asset_type == asset_type and a.is_market_benchmark),
        None,
    )
    if benchmark is None:
        return None
    candles = candles_repo.get_candles(db, benchmark.symbol, timeframe, ascending=False, limit=400)
    if len(candles) < 200:
        return None
    df = candles_repo.candles_to_df(candles)
    return detect_regime(df, symbol=benchmark.symbol, timeframe=timeframe).regime


def run_signals(db: Session, *, timeframe: str | None = None) -> list[Signal]:
    store = get_config_store()
    kronos: KronosConfig = store.kronos()
    strategy: StrategyConfig = store.strategy()
    risk: RiskConfig = store.risk()
    timeframe = timeframe or store.timeframes().get("default", "1h")
    adapter = KronosAdapter(kronos)

    market_regimes = {
        "crypto": _market_regime(db, "crypto", timeframe, kronos),
        "stock": _market_regime(db, "stock", timeframe, kronos),
    }

    saved: list[Signal] = []
    for asset in store.all_assets():
        if not asset.enabled:
            continue
        candles = candles_repo.get_candles(
            db, asset.symbol, timeframe, ascending=False, limit=kronos.context_length + 10
        )
        if len(candles) < kronos.context_length:
            log.warning("signal_skip_short_history", symbol=asset.symbol, have=len(candles))
            continue
        df = candles_repo.candles_to_df(candles)

        dist = adapter.forecast(df, symbol=asset.symbol, timeframe=timeframe)
        frun = forecasts_repo.save_forecast(db, dist.to_dict())

        regime = detect_regime(
            df, symbol=asset.symbol, timeframe=timeframe,
            market_regime=market_regimes.get(asset.asset_type),
        )
        regime_row = signals_repo.save_regime_snapshot(db, regime.to_dict())

        signal = score_signal(
            forecast=dist, regime=regime, df=df, strategy=strategy, risk=risk
        )
        payload = signal.to_dict()
        payload["forecast_run_id"] = frun.id
        payload["regime_snapshot_id"] = regime_row.id
        row = signals_repo.save_signal(db, payload, signal.explanations)
        saved.append(row)

    _auto_execute_candidates(db, saved, risk)
    log.info("signals_run_complete", count=len(saved), timeframe=timeframe)
    return saved


def manage_paper(db: Session) -> int:
    risk = get_config_store().risk()
    return ledger.auto_manage_open_orders(db, risk=risk)


def run_fast_rescore(db: Session, *, timeframe: str | None = None) -> list[Signal]:
    """Fast rescore using latest candles but preserving the previous expensive forecast."""
    store = get_config_store()
    kronos: KronosConfig = store.kronos()
    strategy: StrategyConfig = store.strategy()
    risk: RiskConfig = store.risk()
    timeframe = timeframe or store.timeframes().get("default", "1h")

    market_regimes = {
        "crypto": _market_regime(db, "crypto", timeframe, kronos),
        "stock": _market_regime(db, "stock", timeframe, kronos),
    }

    saved: list[Signal] = []
    for asset in store.all_assets():
        if not asset.enabled:
            continue

        run = forecasts_repo.get_latest_forecast(db, asset.symbol, timeframe)
        if not run:
            continue

        candles = candles_repo.get_candles(
            db, asset.symbol, timeframe, ascending=False, limit=kronos.context_length + 10
        )
        if len(candles) < kronos.context_length:
            continue
        df = candles_repo.candles_to_df(candles)

        dist = forecasts_repo.reconstruct_forecast_distribution(db, run)

        regime = detect_regime(
            df, symbol=asset.symbol, timeframe=timeframe,
            market_regime=market_regimes.get(asset.asset_type),
        )
        regime_row = signals_repo.save_regime_snapshot(db, regime.to_dict())

        signal = score_signal(
            forecast=dist, regime=regime, df=df, strategy=strategy, risk=risk
        )
        payload = signal.to_dict()
        payload["forecast_run_id"] = run.id
        payload["regime_snapshot_id"] = regime_row.id
        # Override the as_of timestamp so the signal reflects the latest candle's time
        payload["as_of"] = regime.as_of
        row = signals_repo.save_signal(db, payload, signal.explanations)
        saved.append(row)

    _auto_execute_candidates(db, saved, risk)
    log.info("fast_rescore_complete", count=len(saved), timeframe=timeframe)
    return saved


def _auto_execute_candidates(db: Session, signals: list[Signal], risk: RiskConfig) -> None:
    for sig in signals:
        if sig.status in (TradeCandidateStatus.LONG_CANDIDATE.value, TradeCandidateStatus.SHORT_CANDIDATE.value):
            existing = paper_trades_repo.open_orders_for_symbol(db, sig.symbol)
            if existing:
                continue
            
            side = Side(sig.side) if sig.side else None
            if not side:
                continue
                
            try:
                ledger.open_paper_order(
                    db,
                    symbol=sig.symbol,
                    side=side,
                    risk=risk,
                    timeframe=sig.timeframe,
                    signal_id=sig.id,
                    forecast_id=sig.forecast_run_id,
                    thesis=f"Auto-executed on {sig.status}",
                )
            except Exception as e:
                log.warning("auto_execute_failed", symbol=sig.symbol, error=str(e))
