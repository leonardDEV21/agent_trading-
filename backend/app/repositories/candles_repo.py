"""Candle persistence and retrieval.

Enforces the data-contract uniqueness rule (no duplicate candle for a given
symbol/exchange/timeframe/timestamp_open) on write, and returns clean pandas
DataFrames for the forecast/backtest pipelines.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.symbols import normalize_symbol
from app.data.contracts.candle_schema import Candle as CandleContract
from app.db.models import Candle


def upsert_candles(db: Session, candles: list[CandleContract]) -> int:
    """Insert validated candles, ignoring duplicates. Returns rows inserted.

    Uses ON CONFLICT DO NOTHING against uq_candle_identity so re-ingesting an
    overlapping window is safe and idempotent.
    """
    if not candles:
        return 0

    rows = [
        {
            "symbol": c.symbol,
            "exchange": c.exchange,
            "asset_type": c.asset_type,
            "timeframe": c.timeframe,
            "timestamp_open": c.timestamp_open,
            "timestamp_close": c.timestamp_close,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
            "quote_volume": c.quote_volume,
            "trade_count": c.trade_count,
            "source": c.source,
        }
        for c in candles
    ]

    stmt = pg_insert(Candle).values(rows)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_candle_identity")
    result = db.execute(stmt)
    return result.rowcount or 0


def get_candles(
    db: Session,
    symbol: str,
    timeframe: str,
    *,
    exchange: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int | None = None,
    ascending: bool = True,
) -> list[Candle]:
    symbol = normalize_symbol(symbol)
    conds = [Candle.symbol == symbol, Candle.timeframe == timeframe]
    if exchange:
        conds.append(Candle.exchange == exchange)
    if start:
        conds.append(Candle.timestamp_open >= start)
    if end:
        conds.append(Candle.timestamp_open <= end)

    order = Candle.timestamp_open.asc() if ascending else Candle.timestamp_open.desc()
    stmt = select(Candle).where(and_(*conds)).order_by(order)
    if limit:
        stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())


def get_latest_candle(db: Session, symbol: str, timeframe: str) -> Candle | None:
    rows = get_candles(db, symbol, timeframe, limit=1, ascending=False)
    return rows[0] if rows else None


def candles_to_df(candles: list[Candle]) -> pd.DataFrame:
    """Convert ORM candles to a tidy, UTC-indexed OHLCV DataFrame.

    Adds an ``amount`` column (quote volume) because Kronos.predict() expects it.
    """
    if not candles:
        return pd.DataFrame(
            columns=["open", "high", "low", "close", "volume", "amount"]
        )
    data = {
        "timestamp_open": [c.timestamp_open for c in candles],
        "open": [float(c.open) for c in candles],
        "high": [float(c.high) for c in candles],
        "low": [float(c.low) for c in candles],
        "close": [float(c.close) for c in candles],
        "volume": [float(c.volume) for c in candles],
        "amount": [
            float(c.quote_volume) if c.quote_volume is not None else float(c.close) * float(c.volume)
            for c in candles
        ],
    }
    df = pd.DataFrame(data)
    df = df.set_index("timestamp_open").sort_index()
    return df


def count_candles(db: Session, symbol: str, timeframe: str) -> int:
    symbol = normalize_symbol(symbol)
    stmt = select(Candle.id).where(Candle.symbol == symbol, Candle.timeframe == timeframe)
    return len(list(db.execute(stmt).scalars().all()))
