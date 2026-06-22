"""Exposure limits + the trade-risk coordinator (assess_trade).

This is the single gate every new entry passes through (paper engine and
backtester both call it). It composes the stop, take-profit and sizing engines
and enforces account-level limits, returning a fully reason-coded decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import RiskConfig
from app.core.constants import ReasonCode, Side, TradeCandidateStatus
from app.risk.position_sizing import size_position
from app.risk.stop_engine import compute_stop
from app.risk.take_profit_engine import compute_take_profit, reward_risk_ratio


@dataclass
class OpenPositionView:
    symbol: str
    beta_group: str | None = None


@dataclass
class RiskDecision:
    allowed: bool
    status: TradeCandidateStatus
    reason_codes: list[str] = field(default_factory=list)
    side: Side | None = None
    entry: float | None = None
    stop: float | None = None
    take_profit: float | None = None
    size: float = 0.0
    notional: float = 0.0
    risk_amount: float = 0.0
    reward_risk: float = 0.0


def correlated_count(open_positions: list[OpenPositionView], beta_group: str | None) -> int:
    if not beta_group:
        return 0
    return sum(1 for p in open_positions if p.beta_group == beta_group)


def assess_trade(
    *,
    side: Side,
    entry: float,
    atr: float,
    invalidation_level: float | None,
    forecast_target: float | None,
    beta_group: str | None,
    open_positions: list[OpenPositionView],
    daily_pnl_pct: float,
    kill_switch_active: bool,
    risk: RiskConfig,
) -> RiskDecision:
    """Decide whether a candidate may become a (paper) trade and size it."""
    reasons: list[str] = []
    blocked = lambda rc: RiskDecision(  # noqa: E731
        allowed=False, status=TradeCandidateStatus.BLOCKED_BY_RISK, reason_codes=[rc], side=side,
        entry=entry,
    )

    # 1. kill switch
    if kill_switch_active:
        return blocked(ReasonCode.RISK_KILL_SWITCH_ACTIVE.value)

    # 2. daily loss limit
    if daily_pnl_pct <= -abs(risk.max_daily_loss):
        return blocked(ReasonCode.RISK_DAILY_LOSS_LIMIT.value)

    # 3. max open positions
    if len(open_positions) >= risk.max_open_positions:
        return blocked(ReasonCode.RISK_MAX_OPEN_POSITIONS.value)

    # 4. correlated exposure
    if correlated_count(open_positions, beta_group) >= risk.max_correlated_positions:
        return blocked(ReasonCode.RISK_MAX_CORRELATED.value)

    # 5. leverage policy
    if not risk.allow_leverage and risk.max_leverage > 1:
        reasons.append(ReasonCode.RISK_LEVERAGE_DISABLED.value)

    # 6. stop (mandatory)
    stop = compute_stop(
        side=side, entry=entry, atr=atr, invalidation_level=invalidation_level,
        min_stop_distance_pct=risk.min_stop_distance_pct,
    )
    dist = abs(entry - stop)
    if dist < entry * risk.min_stop_distance_pct * 0.999:
        return blocked(ReasonCode.RISK_STOP_TOO_TIGHT.value)

    # 7. take profit
    take_profit = None
    if risk.require_take_profit:
        take_profit = compute_take_profit(
            side=side, entry=entry, stop=stop,
            min_reward_risk_ratio=risk.min_reward_risk_ratio, forecast_target=forecast_target,
        )
        rr = reward_risk_ratio(side, entry, stop, take_profit)
        if rr < risk.min_reward_risk_ratio - 1e-9:
            return blocked(ReasonCode.RISK_REWARD_RISK_TOO_LOW.value)
    else:
        rr = 0.0

    # 8. sizing
    sizing = size_position(
        side=side, account_size=risk.account_size, risk_per_trade=risk.risk_per_trade,
        entry=entry, stop=stop, allow_leverage=risk.allow_leverage,
        max_leverage=risk.max_leverage,
    )
    reasons.extend(sizing.reason_codes)
    if not sizing.valid:
        return RiskDecision(
            allowed=False, status=TradeCandidateStatus.BLOCKED_BY_RISK,
            reason_codes=reasons or [ReasonCode.RISK_SIZE_BELOW_MIN_NOTIONAL.value],
            side=side, entry=entry, stop=stop, take_profit=take_profit,
        )

    return RiskDecision(
        allowed=True,
        status=TradeCandidateStatus.LONG_CANDIDATE
        if side == Side.LONG
        else TradeCandidateStatus.SHORT_CANDIDATE,
        reason_codes=reasons,
        side=side,
        entry=round(entry, 8),
        stop=stop,
        take_profit=take_profit,
        size=sizing.size,
        notional=sizing.notional,
        risk_amount=sizing.risk_amount,
        reward_risk=round(rr, 3),
    )
