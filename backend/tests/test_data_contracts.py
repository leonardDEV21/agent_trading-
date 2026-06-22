"""Candle data-contract validation, duplicate prevention, gap detection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import DataContractError
from app.data.contracts.candle_schema import Candle, candle_issues
from app.data.ingestion.data_validator import validate_candles
from app.data.ingestion.gap_detector import detect_gaps

UTC = timezone.utc


def _candle(ts, o=100, h=110, low=90, c=105, v=10):
    return Candle(
        symbol="BTC/USDT", exchange="binance", asset_type="crypto", timeframe="1h",
        timestamp_open=ts, timestamp_close=ts + timedelta(hours=1),
        open=o, high=h, low=low, close=c, volume=v, source="test",
    )


def test_valid_candle_passes():
    c = _candle(datetime(2025, 1, 1, tzinfo=UTC))
    assert c.high >= c.open and c.low <= c.close


def test_high_below_open_rejected():
    with pytest.raises(DataContractError):
        _candle(datetime(2025, 1, 1, tzinfo=UTC), o=100, h=95, low=90, c=98)


def test_negative_price_rejected():
    with pytest.raises(DataContractError):
        _candle(datetime(2025, 1, 1, tzinfo=UTC), o=-1, h=110, low=90, c=105)


def test_zero_volume_allowed_but_negative_rejected():
    assert candle_issues(o=100, h=110, low=90, c=105, v=0) == []
    assert any("volume" in m for m in candle_issues(o=100, h=110, low=90, c=105, v=-5))


def test_timestamps_normalized_to_utc():
    naive = datetime(2025, 1, 1, 0, 0, 0)
    c = _candle(naive)
    assert c.timestamp_open.tzinfo is not None


def test_duplicate_detection():
    ts = datetime(2025, 1, 1, tzinfo=UTC)
    candles = [_candle(ts), _candle(ts)]  # same identity
    report = validate_candles(candles)
    assert report.duplicates == 1
    assert not report.ok


def test_gap_detection():
    base = datetime(2025, 1, 1, tzinfo=UTC)
    opens = [base, base + timedelta(hours=1), base + timedelta(hours=4)]  # missing h2,h3
    gaps = detect_gaps(opens, "1h")
    assert len(gaps) == 1
    assert gaps[0].missing_candles == 2


def test_no_gap_when_contiguous():
    base = datetime(2025, 1, 1, tzinfo=UTC)
    opens = [base + timedelta(hours=i) for i in range(5)]
    assert detect_gaps(opens, "1h") == []
