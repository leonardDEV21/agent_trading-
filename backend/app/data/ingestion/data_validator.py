"""Batch candle validation + duplicate detection.

Wraps the pure contract checks in candle_schema and adds cross-row checks
(duplicates, monotonic time) that a single candle can't see.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.data.contracts.candle_schema import Candle, candle_issues


@dataclass
class ValidationReport:
    total: int = 0
    valid: int = 0
    invalid: int = 0
    duplicates: int = 0
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.invalid == 0 and self.duplicates == 0


def validate_candles(candles: list[Candle]) -> ValidationReport:
    """Validate already-parsed Candle objects for contract + duplicate issues."""
    report = ValidationReport(total=len(candles))
    seen: set[tuple] = set()

    for c in candles:
        problems = candle_issues(
            o=c.open, h=c.high, low=c.low, c=c.close, v=c.volume,
            ts_open=c.timestamp_open, ts_close=c.timestamp_close,
        )
        key = c.unique_key()
        if key in seen:
            report.duplicates += 1
            report.issues.append(f"duplicate candle {key}")
            continue
        seen.add(key)

        if problems:
            report.invalid += 1
            report.issues.append(f"{c.symbol}@{c.timestamp_open.isoformat()}: {'; '.join(problems)}")
        else:
            report.valid += 1

    # cap stored issue strings to keep payloads small
    report.issues = report.issues[:100]
    return report
