"""Rank scored signals into the buckets the dashboard renders."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.constants import Regime, TradeCandidateStatus
from app.strategy.signal_scoring import SignalResult


@dataclass
class RankedSignals:
    long_candidates: list[SignalResult] = field(default_factory=list)
    short_candidates: list[SignalResult] = field(default_factory=list)
    volatility_expansion: list[SignalResult] = field(default_factory=list)
    watch: list[SignalResult] = field(default_factory=list)
    blocked: list[SignalResult] = field(default_factory=list)
    no_edge: list[SignalResult] = field(default_factory=list)


_BLOCKED = {
    TradeCandidateStatus.BLOCKED_BY_REGIME,
    TradeCandidateStatus.BLOCKED_BY_RISK,
    TradeCandidateStatus.BLOCKED_BY_LATE_ENTRY,
    TradeCandidateStatus.BLOCKED_BY_COSTS,
    TradeCandidateStatus.BLOCKED_BY_UNCERTAINTY,
}


def rank_signals(
    signals: list[SignalResult], regimes: dict[str, Regime] | None = None
) -> RankedSignals:
    """Bucket and sort signals. Candidates are sorted by edge_score desc."""
    regimes = regimes or {}
    out = RankedSignals()

    for s in signals:
        if s.status == TradeCandidateStatus.LONG_CANDIDATE:
            out.long_candidates.append(s)
        elif s.status == TradeCandidateStatus.SHORT_CANDIDATE:
            out.short_candidates.append(s)
        elif s.status in _BLOCKED:
            out.blocked.append(s)
        elif s.status == TradeCandidateStatus.WATCH:
            out.watch.append(s)
        else:
            out.no_edge.append(s)

        if regimes.get(s.symbol) == Regime.VOLATILITY_EXPANSION:
            out.volatility_expansion.append(s)

    out.long_candidates.sort(key=lambda x: x.edge_score, reverse=True)
    out.short_candidates.sort(key=lambda x: x.edge_score, reverse=True)
    out.watch.sort(key=lambda x: x.edge_score, reverse=True)
    return out
