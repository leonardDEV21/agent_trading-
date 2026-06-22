"""Timeframe helpers. All timestamps are timezone-aware UTC.

The data contract requires UTC throughout (DATA_CONTRACT.md). These helpers are
the only place timeframe math lives so the ingestion, forecast and backtest
pipelines all agree on candle boundaries.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# seconds per supported timeframe and the periods-per-year used for
# annualizing returns/Sharpe. Mirror configs/timeframes.json.
_TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}

_ANNUALIZATION: dict[str, float] = {
    "1m": 525600,
    "5m": 105120,
    "15m": 35040,
    "30m": 17520,
    "1h": 8760,
    "4h": 2190,
    "1d": 365,
}


def timeframe_seconds(timeframe: str) -> int:
    try:
        return _TIMEFRAME_SECONDS[timeframe]
    except KeyError as exc:  # pragma: no cover - guarded by config
        raise ValueError(f"Unsupported timeframe: {timeframe}") from exc


def timeframe_delta(timeframe: str) -> timedelta:
    return timedelta(seconds=timeframe_seconds(timeframe))


def annualization_periods(timeframe: str) -> float:
    return _ANNUALIZATION.get(timeframe, 365.0)


def ensure_utc(ts: datetime) -> datetime:
    """Return a tz-aware UTC datetime. Naive input is assumed already-UTC."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def floor_to_timeframe(ts: datetime, timeframe: str) -> datetime:
    """Floor a timestamp down to the start of its candle bucket (UTC)."""
    ts = ensure_utc(ts)
    secs = timeframe_seconds(timeframe)
    epoch = int(ts.timestamp())
    floored = epoch - (epoch % secs)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


def future_timestamps(last_open: datetime, timeframe: str, horizon: int) -> list[datetime]:
    """Generate the next ``horizon`` candle-open timestamps after ``last_open``.

    Used to build the ``y_timestamp`` series Kronos.predict() requires.
    """
    delta = timeframe_delta(timeframe)
    last_open = ensure_utc(last_open)
    return [last_open + delta * (i + 1) for i in range(horizon)]


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)
