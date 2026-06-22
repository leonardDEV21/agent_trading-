"""SQLAlchemy ORM models — the full database schema.

Tables: assets, candles, data_gaps, forecast_runs, forecast_paths, signals,
signal_explanations, regime_snapshots, backtest_runs, backtest_trades,
backtest_equity, paper_orders, paper_positions, risk_events, scheduler_runs,
configs, audit_logs.

Design notes:
- All timestamps are stored as timezone-aware UTC (DateTime(timezone=True)).
- Money/price columns use Numeric to avoid binary-float drift in the ledger.
- JSON columns hold reason-code lists, forecast path arrays and config snapshots.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utcnow_col() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("symbol", "exchange", name="uq_asset_symbol_exchange"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    is_market_benchmark: Mapped[bool] = mapped_column(Boolean, default=False)
    beta_group: Mapped[str | None] = mapped_column(String(64), index=True)
    min_notional_usd: Mapped[float] = mapped_column(Float, default=10.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _utcnow_col()


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint(
            "symbol", "exchange", "timeframe", "timestamp_open", name="uq_candle_identity"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), index=True, nullable=False)
    timestamp_open: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    timestamp_close: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Numeric(24, 10), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(24, 10), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(24, 10), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(24, 10), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(28, 10), nullable=False)
    quote_volume: Mapped[float | None] = mapped_column(Numeric(28, 10))
    trade_count: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(32), default="unknown")
    ingested_at: Mapped[datetime] = _utcnow_col()


class DataGap(Base):
    __tablename__ = "data_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    gap_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gap_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    missing_candles: Mapped[int] = mapped_column(Integer, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    detected_at: Mapped[datetime] = _utcnow_col()


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = _utcnow_col()
    context_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    context_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    horizon: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # forecast mode is explicit and queryable so mock output is never confused.
    mode: Mapped[str] = mapped_column(String(8), nullable=False)  # real | mock
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_config_hash: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    # summary statistics (full per-path arrays live in forecast_paths)
    last_close: Mapped[float] = mapped_column(Numeric(24, 10), nullable=False)
    p_up: Mapped[float] = mapped_column(Float, nullable=False)
    p_down: Mapped[float] = mapped_column(Float, nullable=False)
    median_return: Mapped[float] = mapped_column(Float, nullable=False)
    q10_return: Mapped[float] = mapped_column(Float, nullable=False)
    q25_return: Mapped[float] = mapped_column(Float, nullable=False)
    q75_return: Mapped[float] = mapped_column(Float, nullable=False)
    q90_return: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_volatility: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_volatility_ratio: Mapped[float] = mapped_column(Float, nullable=False)

    paths: Mapped[list[ForecastPath]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ForecastPath(Base):
    """Quantile paths and (optionally) raw sample paths for a forecast run."""

    __tablename__ = "forecast_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forecast_run_id: Mapped[int] = mapped_column(ForeignKey("forecast_runs.id", ondelete="CASCADE"))
    # one of: median, q10, q25, q75, q90, sample
    path_type: Mapped[str] = mapped_column(String(16), nullable=False)
    sample_index: Mapped[int | None] = mapped_column(Integer)
    # JSON array of close prices, length == horizon
    values: Mapped[list[float]] = mapped_column(JSON, nullable=False)

    run: Mapped[ForecastRun] = relationship(back_populates="paths")


class RegimeSnapshot(Base):
    __tablename__ = "regime_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    regime: Mapped[str] = mapped_column(String(32), nullable=False)
    regime_score: Mapped[float] = mapped_column(Float, nullable=False)
    market_regime: Mapped[str | None] = mapped_column(String(32))
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = _utcnow_col()


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    forecast_run_id: Mapped[int | None] = mapped_column(ForeignKey("forecast_runs.id"))
    regime_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("regime_snapshots.id"))

    side: Mapped[str | None] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    confidence_label: Mapped[str] = mapped_column(String(8), default="none")

    p_up: Mapped[float] = mapped_column(Float, nullable=False)
    p_down: Mapped[float] = mapped_column(Float, nullable=False)
    median_return: Mapped[float] = mapped_column(Float, nullable=False)
    q10_return: Mapped[float] = mapped_column(Float, nullable=False)
    q90_return: Mapped[float] = mapped_column(Float, nullable=False)
    asymmetry_score: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_volatility_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    path_quality: Mapped[float] = mapped_column(Float, nullable=False)
    trend_alignment: Mapped[float] = mapped_column(Float, nullable=False)
    regime_score: Mapped[float] = mapped_column(Float, nullable=False)
    liquidity_score: Mapped[float] = mapped_column(Float, nullable=False)
    cost_adjusted_edge: Mapped[float] = mapped_column(Float, nullable=False)
    edge_score: Mapped[float] = mapped_column(Float, index=True, nullable=False)

    entry_zone_low: Mapped[float | None] = mapped_column(Numeric(24, 10))
    entry_zone_high: Mapped[float | None] = mapped_column(Numeric(24, 10))
    invalidation_level: Mapped[float | None] = mapped_column(Numeric(24, 10))

    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    edge_formula_version: Mapped[str] = mapped_column(String(16), default="v1")
    created_at: Mapped[datetime] = _utcnow_col()

    explanations: Mapped[list[SignalExplanation]] = relationship(
        back_populates="signal", cascade="all, delete-orphan"
    )


class SignalExplanation(Base):
    __tablename__ = "signal_explanations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"))
    factor: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float | None] = mapped_column(Float)
    threshold: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    text: Mapped[str] = mapped_column(Text, default="")

    signal: Mapped[Signal] = relationship(back_populates="explanations")


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = _utcnow_col()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|done|error
    symbols: Mapped[list[str]] = mapped_column(JSON, default=list)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    config_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    strategy_config_hash: Mapped[str] = mapped_column(String(32), default="")
    kronos_config_hash: Mapped[str] = mapped_column(String(32), default="")
    forecast_mode: Mapped[str] = mapped_column(String(8), default="mock")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    baseline_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)

    trades: Mapped[list[BacktestTrade]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    equity_points: Mapped[list[BacktestEquity]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    backtest_run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(24, 10), nullable=False)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_price: Mapped[float | None] = mapped_column(Numeric(24, 10))
    stop_loss: Mapped[float] = mapped_column(Numeric(24, 10), nullable=False)
    take_profit: Mapped[float | None] = mapped_column(Numeric(24, 10))
    size: Mapped[float] = mapped_column(Numeric(28, 10), nullable=False)
    risk_amount: Mapped[float] = mapped_column(Float, nullable=False)
    gross_pnl: Mapped[float | None] = mapped_column(Float)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    slippage: Mapped[float] = mapped_column(Float, default=0.0)
    net_pnl: Mapped[float | None] = mapped_column(Float)
    regime: Mapped[str | None] = mapped_column(String(32))
    exit_reason: Mapped[str | None] = mapped_column(String(32))
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)

    run: Mapped[BacktestRun] = relationship(back_populates="trades")


class BacktestEquity(Base):
    __tablename__ = "backtest_equity"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    backtest_run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id", ondelete="CASCADE"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    equity: Mapped[float] = mapped_column(Float, nullable=False)
    drawdown: Mapped[float] = mapped_column(Float, default=0.0)

    run: Mapped[BacktestRun] = relationship(back_populates="equity_points")


class PaperOrder(Base):
    __tablename__ = "paper_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_order_id: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(24, 10), nullable=False)
    stop_loss: Mapped[float] = mapped_column(Numeric(24, 10), nullable=False)
    take_profit: Mapped[float | None] = mapped_column(Numeric(24, 10))
    size: Mapped[float] = mapped_column(Numeric(28, 10), nullable=False)
    risk_amount: Mapped[float] = mapped_column(Float, nullable=False)
    thesis: Mapped[str] = mapped_column(Text, default="")
    forecast_id: Mapped[int | None] = mapped_column(ForeignKey("forecast_runs.id"))
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"))
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_price: Mapped[float | None] = mapped_column(Numeric(24, 10))
    realized_pnl: Mapped[float | None] = mapped_column(Float)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    slippage: Mapped[float] = mapped_column(Float, default=0.0)
    exit_reason: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = _utcnow_col()


class PaperPosition(Base):
    """Aggregated open exposure per symbol (derived from open orders)."""

    __tablename__ = "paper_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    size: Mapped[float] = mapped_column(Numeric(28, 10), default=0.0)
    avg_entry_price: Mapped[float] = mapped_column(Numeric(24, 10), default=0.0)
    open_risk_amount: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = _utcnow_col()


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    trigger: Mapped[str | None] = mapped_column(String(32))
    symbol: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _utcnow_col()
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SchedulerRun(Base):
    __tablename__ = "scheduler_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    started_at: Mapped[datetime] = _utcnow_col()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="running")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)


class Config(Base):
    """Versioned config snapshots (audit trail of what produced each result)."""

    __tablename__ = "configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = _utcnow_col()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor: Mapped[str] = mapped_column(String(64), default="system")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = _utcnow_col()
