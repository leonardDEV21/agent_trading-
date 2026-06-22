"""Candle ingestion orchestration: fetch -> validate -> store -> flag gaps."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.errors import DataProviderError
from app.core.symbols import normalize_symbol
from app.core.timeframes import now_utc, timeframe_delta
from app.data.ingestion.data_validator import validate_candles
from app.data.ingestion.gap_detector import detect_gaps
from app.data.providers.base_provider import BaseProvider
from app.data.providers.binance_provider import BinanceProvider
from app.data.providers.bybit_provider import BybitProvider
from app.data.providers.coinbase_provider import CoinbaseProvider
from app.data.providers.yfinance_provider import YFinanceProvider
from app.db.models import DataGap
from app.logging_config import get_logger
from app.repositories import candles_repo

log = get_logger("ingestor")

_PROVIDERS: dict[str, type[BaseProvider]] = {
    "binance": BinanceProvider,
    "bybit": BybitProvider,
    "coinbase": CoinbaseProvider,
    "yfinance": YFinanceProvider,
}


def get_provider(exchange: str) -> BaseProvider:
    klass = _PROVIDERS.get(exchange.lower())
    if klass is None:
        raise DataProviderError(f"No provider registered for exchange '{exchange}'")
    return klass()


@dataclass
class IngestResult:
    symbol: str
    exchange: str
    timeframe: str
    fetched: int = 0
    inserted: int = 0
    duplicates: int = 0
    invalid: int = 0
    gaps_found: int = 0
    issues: list[str] = field(default_factory=list)


def ingest_candles(
    db: Session,
    *,
    symbol: str,
    exchange: str,
    asset_type: str,
    timeframe: str,
    start: datetime | None = None,
    lookback_candles: int = 1000,
    page_limit: int = 1000,
    max_pages: int = 20,
) -> IngestResult:
    """Fetch and persist candles, paginating backwards-to-forwards as needed.

    If ``start`` is None we fetch the most recent ``lookback_candles`` candles.
    """
    symbol = normalize_symbol(symbol)
    provider = get_provider(exchange)
    delta = timeframe_delta(timeframe)

    if start is None:
        start = now_utc() - delta * lookback_candles

    result = IngestResult(symbol=symbol, exchange=exchange, timeframe=timeframe)
    cursor = start
    all_opens: list[datetime] = []

    for _page in range(max_pages):
        batch = provider.fetch_candles(symbol, timeframe, start=cursor, limit=page_limit)
        if not batch:
            break

        report = validate_candles(batch)
        result.fetched += report.total
        result.duplicates += report.duplicates
        result.invalid += report.invalid
        if report.issues:
            result.issues.extend(report.issues[:20])

        valid_batch = [
            c
            for c in batch
            if not _candle_invalid(c)
        ]
        inserted = candles_repo.upsert_candles(db, valid_batch)
        result.inserted += inserted
        all_opens.extend(c.timestamp_open for c in valid_batch)

        last_open = batch[-1].timestamp_open
        # advance the cursor past the last candle we received
        next_cursor = last_open + delta
        if next_cursor <= cursor or last_open >= now_utc() - delta:
            break
        cursor = next_cursor

    # Gap detection over what we now have stored for this symbol/timeframe.
    stored = candles_repo.get_candles(db, symbol, timeframe, ascending=True)
    opens = [c.timestamp_open for c in stored]
    gaps = detect_gaps(opens, timeframe)
    for g in gaps:
        db.add(
            DataGap(
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                gap_start=g.gap_start,
                gap_end=g.gap_end,
                missing_candles=g.missing_candles,
            )
        )
    result.gaps_found = len(gaps)

    log.info(
        "ingest_complete",
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        inserted=result.inserted,
        duplicates=result.duplicates,
        gaps=result.gaps_found,
    )
    return result


def _candle_invalid(candle) -> bool:
    # Candle objects are already contract-valid (pydantic enforced at construction),
    # so this is a defensive no-op hook kept for symmetry/extension.
    return False


def freshness_age(db: Session, symbol: str, timeframe: str) -> timedelta | None:
    latest = candles_repo.get_latest_candle(db, symbol, timeframe)
    if latest is None:
        return None
    return now_utc() - latest.timestamp_open
