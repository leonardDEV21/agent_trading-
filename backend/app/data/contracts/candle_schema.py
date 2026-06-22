"""Canonical candle schema and validation (see DATA_CONTRACT.md).

This module is the single authority on what a *valid* candle is. Ingestion,
backtesting and the API all validate through here so bad data can never reach
the forecast model or the ledger.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.errors import DataContractError
from app.core.symbols import normalize_symbol
from app.core.timeframes import ensure_utc


class Candle(BaseModel):
    """A single validated OHLCV candle in canonical form."""

    symbol: str
    exchange: str
    asset_type: str
    timeframe: str
    timestamp_open: datetime
    timestamp_close: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float | None = None
    trade_count: int | None = None
    source: str = "unknown"
    ingested_at: datetime | None = None

    @field_validator("symbol")
    @classmethod
    def _norm_symbol(cls, v: str) -> str:
        return normalize_symbol(v)

    @field_validator("timestamp_open", "timestamp_close", "ingested_at")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return ensure_utc(v) if v is not None else None

    @model_validator(mode="after")
    def _validate_contract(self) -> Candle:
        issues = candle_issues(
            o=self.open,
            h=self.high,
            low=self.low,
            c=self.close,
            v=self.volume,
            ts_open=self.timestamp_open,
            ts_close=self.timestamp_close,
        )
        if issues:
            raise DataContractError(
                f"Candle violates data contract: {'; '.join(issues)}",
                detail={"symbol": self.symbol, "timestamp_open": self.timestamp_open.isoformat(),
                        "issues": issues},
            )
        return self

    def unique_key(self) -> tuple[str, str, str, datetime]:
        return (self.symbol, self.exchange, self.timeframe, self.timestamp_open)


def candle_issues(
    *,
    o: float,
    h: float,
    low: float,
    c: float,
    v: float,
    ts_open: datetime | None = None,
    ts_close: datetime | None = None,
) -> list[str]:
    """Return a list of human-readable contract violations (empty == valid).

    Pure function so it can be reused by the DataFrame validator and unit tests
    without constructing model instances.
    """
    issues: list[str] = []

    # positivity: O/H/L/C must be > 0; volume may be 0 but never negative.
    for name, val in (("open", o), ("high", h), ("low", low), ("close", c)):
        if val is None:
            issues.append(f"{name} is null")
        elif val <= 0:
            issues.append(f"{name} must be > 0 (got {val})")
    if v is None:
        issues.append("volume is null")
    elif v < 0:
        issues.append(f"volume must be >= 0 (got {v})")

    # OHLC relationships
    if None not in (o, h, low, c):
        if h < max(o, c, low):
            issues.append(f"high {h} must be >= max(open, close, low)")
        if low > min(o, c, h):
            issues.append(f"low {low} must be <= min(open, close, high)")

    # timestamp ordering
    if ts_open is not None and ts_close is not None and ts_close <= ts_open:
        issues.append("timestamp_close must be after timestamp_open")

    return issues


# Field list reused by repositories / migrations / docs.
CANDLE_FIELDS = list(Candle.model_fields.keys())
