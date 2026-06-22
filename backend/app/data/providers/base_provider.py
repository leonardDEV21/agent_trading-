"""Market-data provider interface + shared CCXT implementation.

Exchange integration is isolated here. Strategy/forecast code never imports
ccxt or yfinance directly — it asks a provider for validated Candle objects.
"""

from __future__ import annotations

import abc
from datetime import datetime

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.errors import DataProviderError
from app.core.symbols import normalize_symbol
from app.core.timeframes import ensure_utc, timeframe_delta
from app.data.contracts.candle_schema import Candle
from app.logging_config import get_logger

log = get_logger("provider")


class BaseProvider(abc.ABC):
    """Abstract market-data provider."""

    name: str = "base"
    asset_type: str = "crypto"

    @abc.abstractmethod
    def fetch_candles(
        self, symbol: str, timeframe: str, *, start: datetime | None = None, limit: int = 1000
    ) -> list[Candle]:
        """Return validated candles ascending by time. Raise DataProviderError on failure."""

    def supports(self, symbol: str) -> bool:  # pragma: no cover - thin default
        return True


class CCXTProvider(BaseProvider):
    """Generic CCXT-backed crypto provider. Subclasses set ``exchange_id``."""

    exchange_id: str = ""
    asset_type = "crypto"

    def __init__(self) -> None:
        self.name = self.exchange_id
        self._exchange = None

    def _client(self):
        if self._exchange is not None:
            return self._exchange
        try:
            import ccxt  # imported lazily so the base image need not pin ccxt at import time
        except ImportError as exc:  # pragma: no cover
            raise DataProviderError("ccxt is not installed") from exc
        try:
            klass = getattr(ccxt, self.exchange_id)
        except AttributeError as exc:
            raise DataProviderError(f"Unknown ccxt exchange '{self.exchange_id}'") from exc
        self._exchange = klass({"enableRateLimit": True, "timeout": 20000})
        return self._exchange

    @retry(
        retry=retry_if_exception_type(DataProviderError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def fetch_candles(
        self, symbol: str, timeframe: str, *, start: datetime | None = None, limit: int = 1000
    ) -> list[Candle]:
        symbol = normalize_symbol(symbol)
        client = self._client()
        since_ms = int(ensure_utc(start).timestamp() * 1000) if start else None
        try:
            raw = client.fetch_ohlcv(symbol, timeframe=timeframe, since=since_ms, limit=limit)
        except Exception as exc:  # ccxt raises a wide variety of network errors
            log.warning("ccxt_fetch_failed", exchange=self.exchange_id, symbol=symbol, error=str(exc))
            raise DataProviderError(
                f"{self.exchange_id} fetch_ohlcv failed for {symbol}: {exc}"
            ) from exc

        delta = timeframe_delta(timeframe)
        candles: list[Candle] = []
        for ts_ms, o, h, low, c, v in raw:
            ts_open = ensure_utc(datetime.utcfromtimestamp(ts_ms / 1000))
            candles.append(
                Candle(
                    symbol=symbol,
                    exchange=self.exchange_id,
                    asset_type=self.asset_type,
                    timeframe=timeframe,
                    timestamp_open=ts_open,
                    timestamp_close=ts_open + delta,
                    open=float(o),
                    high=float(h),
                    low=float(low),
                    close=float(c),
                    volume=float(v),
                    quote_volume=None,
                    source=self.exchange_id,
                )
            )
        candles.sort(key=lambda c: c.timestamp_open)
        return candles
