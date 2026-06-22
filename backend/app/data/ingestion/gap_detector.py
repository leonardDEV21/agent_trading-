"""Detect missing-candle gaps in an ascending candle series.

The data contract requires gaps to be detected and flagged (DATA_CONTRACT.md).
Gaps matter because Kronos context must be contiguous; a silent hole produces a
misleading forecast.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.timeframes import timeframe_delta


@dataclass
class Gap:
    gap_start: datetime  # first MISSING candle open
    gap_end: datetime  # last MISSING candle open
    missing_candles: int


def detect_gaps(candle_opens: list[datetime], timeframe: str) -> list[Gap]:
    """Given sorted candle-open timestamps, return the gaps between them."""
    if len(candle_opens) < 2:
        return []
    delta = timeframe_delta(timeframe)
    gaps: list[Gap] = []
    prev = candle_opens[0]
    for ts in candle_opens[1:]:
        expected = prev + delta
        if ts > expected:
            # number of candle slots strictly between prev and ts
            missing = int(round((ts - expected) / delta))
            gaps.append(Gap(gap_start=expected, gap_end=ts - delta, missing_candles=missing))
        prev = ts
    return gaps
