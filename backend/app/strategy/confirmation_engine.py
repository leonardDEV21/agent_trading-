"""Higher-timeframe confirmation layer.

The signal engine already fuses forecast + same-timeframe regime + structure.
This optional layer adds a top-down filter: a candidate can be demoted if the
higher-timeframe (e.g. 4h) regime contradicts it. Keeps multi-timeframe logic in
one place so it is easy to reason about and test.
"""

from __future__ import annotations

from app.core.constants import ReasonCode, Regime, Side, TradeCandidateStatus
from app.strategy.signal_scoring import SignalResult

_HTF_BLOCK_LONG = {Regime.TREND_DOWN, Regime.PANIC}
_HTF_BLOCK_SHORT = {Regime.TREND_UP, Regime.PANIC}


def confirm_with_higher_timeframe(signal: SignalResult, htf_regime: Regime | None) -> SignalResult:
    """Demote a candidate to blocked_by_regime when the HTF regime opposes it."""
    if htf_regime is None or signal.side is None:
        return signal
    if signal.status not in {
        TradeCandidateStatus.LONG_CANDIDATE,
        TradeCandidateStatus.SHORT_CANDIDATE,
    }:
        return signal

    opposes = (signal.side == Side.LONG and htf_regime in _HTF_BLOCK_LONG) or (
        signal.side == Side.SHORT and htf_regime in _HTF_BLOCK_SHORT
    )
    if opposes:
        signal.status = TradeCandidateStatus.BLOCKED_BY_REGIME
        if ReasonCode.REGIME_CONFLICT.value not in signal.reason_codes:
            signal.reason_codes.append(ReasonCode.REGIME_CONFLICT.value)
    return signal
