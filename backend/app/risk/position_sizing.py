"""Risk-based position sizing.

Size is derived from the dollar risk between entry and stop — never from a
fixed notional. With leverage disabled (the default), notional is capped at the
account size, which only ever *reduces* risk below target.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.constants import ReasonCode, Side


@dataclass
class SizingResult:
    size: float
    notional: float
    risk_amount: float
    valid: bool
    reason_codes: list[str] = field(default_factory=list)


def size_position(
    *,
    side: Side,
    account_size: float,
    risk_per_trade: float,
    entry: float,
    stop: float,
    allow_leverage: bool = False,
    max_leverage: int = 1,
    min_notional_usd: float = 10.0,
) -> SizingResult:
    reasons: list[str] = []
    dist = abs(entry - stop)
    if dist <= 0:
        return SizingResult(0.0, 0.0, 0.0, False, [ReasonCode.RISK_NO_STOP.value])

    target_risk = account_size * risk_per_trade
    size = target_risk / dist
    notional = size * entry

    max_notional = account_size * (max_leverage if allow_leverage else 1)
    if notional > max_notional:
        # cap to available capital (no leverage) -> lowers realized risk
        size = max_notional / entry
        notional = size * entry
        if not allow_leverage:
            reasons.append(ReasonCode.RISK_LEVERAGE_DISABLED.value)

    realized_risk = size * dist

    if notional < min_notional_usd:
        reasons.append(ReasonCode.RISK_SIZE_BELOW_MIN_NOTIONAL.value)
        return SizingResult(round(size, 10), round(notional, 6), round(realized_risk, 6), False, reasons)

    return SizingResult(
        size=round(size, 10),
        notional=round(notional, 6),
        risk_amount=round(realized_risk, 6),
        valid=True,
        reason_codes=reasons,
    )
