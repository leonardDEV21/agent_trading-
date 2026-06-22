"""Stock / ETF data via yfinance (optional, rate-limited, disabled by default).

yfinance intraday history is limited (~730 days for 1h). Treat as best-effort.
"""

from __future__ import annotations

from datetime import datetime

from app.core.errors import DataProviderError
from app.core.symbols import normalize_symbol
from app.core.timeframes import ensure_utc, timeframe_delta
from app.data.contracts.candle_schema import Candle
from app.data.providers.base_provider import BaseProvider
from app.logging_config import get_logger

log = get_logger("provider.yfinance")

_INTERVAL_MAP = {"1h": "60m", "1d": "1d", "15m": "15m", "30m": "30m", "5m": "5m"}


class YFinanceProvider(BaseProvider):
    name = "yfinance"
    asset_type = "stock"

    def fetch_candles(
        self, symbol: str, timeframe: str, *, start: datetime | None = None, limit: int = 1000
    ) -> list[Candle]:
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover
            raise DataProviderError("yfinance is not installed") from exc

        interval = _INTERVAL_MAP.get(timeframe)
        if interval is None:
            raise DataProviderError(f"yfinance does not support timeframe {timeframe}")

        period = "730d" if timeframe in {"1h", "30m", "15m"} else "5y"
        ticker = normalize_symbol(symbol).replace("/", "-")
        try:
            df = yf.download(
                ticker, period=period, interval=interval, auto_adjust=False, progress=False
            )
        except Exception as exc:
            raise DataProviderError(f"yfinance download failed for {ticker}: {exc}") from exc

        if df is None or df.empty:
            raise DataProviderError(f"yfinance returned no data for {ticker}")

        delta = timeframe_delta(timeframe)
        candles: list[Candle] = []
        for idx, row in df.iterrows():
            ts_open = ensure_utc(idx.to_pydatetime())
            try:
                candles.append(
                    Candle(
                        symbol=normalize_symbol(symbol),
                        exchange="yfinance",
                        asset_type="stock",
                        timeframe=timeframe,
                        timestamp_open=ts_open,
                        timestamp_close=ts_open + delta,
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=float(row["Volume"]),
                        quote_volume=None,
                        source="yfinance",
                    )
                )
            except Exception as exc:  # skip malformed rows but log them
                log.warning("yfinance_row_skipped", ticker=ticker, error=str(exc))
        candles.sort(key=lambda c: c.timestamp_open)
        if limit and len(candles) > limit:
            candles = candles[-limit:]
        return candles
