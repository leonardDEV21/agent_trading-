"""Signal scoring — edge formula v1 (config-driven, fully reason-coded).

Pipeline per asset:
    forecast distribution + regime + market structure + costs
        -> factor scores
        -> edge_score
        -> trade_candidate_status + reason codes

No raw buy/sell labels. Every output carries a status and the reasons behind it
(AGENTS.md rule 9). All thresholds live in configs/strategy.default.json and are
versioned via ``edge_formula_version``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.config import RiskConfig, StrategyConfig
from app.core.constants import (
    ConfidenceLabel,
    ReasonCode,
    Regime,
    Side,
    TradeCandidateStatus,
)
from app.kronos.forecast_postprocessor import ForecastDistribution
from app.strategy import volatility_engine as ind
from app.strategy.market_structure import StructureResult, evaluate_structure
from app.strategy.regime_detector import RegimeResult

_ALIGNED_LONG = {Regime.TREND_UP, Regime.RANGE}
_ALIGNED_SHORT = {Regime.TREND_DOWN, Regime.RANGE}
_BLOCK_LONG = {Regime.TREND_DOWN, Regime.PANIC}
_BLOCK_SHORT = {Regime.TREND_UP, Regime.PANIC}


@dataclass
class SignalResult:
    symbol: str
    timeframe: str
    as_of: object
    side: Side | None
    status: TradeCandidateStatus
    confidence_label: ConfidenceLabel

    p_up: float
    p_down: float
    median_return: float
    q10_return: float
    q90_return: float
    asymmetry_score: float
    forecast_volatility_ratio: float
    path_quality: float
    trend_alignment: float
    regime_score: float
    liquidity_score: float
    cost_adjusted_edge: float
    edge_score: float

    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    invalidation_level: float | None = None
    reason_codes: list[str] = field(default_factory=list)
    edge_formula_version: str = "v1"
    explanations: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "as_of": self.as_of,
            "side": self.side.value if self.side else None,
            "status": self.status.value,
            "confidence_label": self.confidence_label.value,
            "p_up": self.p_up,
            "p_down": self.p_down,
            "median_return": self.median_return,
            "q10_return": self.q10_return,
            "q90_return": self.q90_return,
            "asymmetry_score": self.asymmetry_score,
            "forecast_volatility_ratio": self.forecast_volatility_ratio,
            "path_quality": self.path_quality,
            "trend_alignment": self.trend_alignment,
            "regime_score": self.regime_score,
            "liquidity_score": self.liquidity_score,
            "cost_adjusted_edge": self.cost_adjusted_edge,
            "edge_score": self.edge_score,
            "entry_zone_low": self.entry_zone_low,
            "entry_zone_high": self.entry_zone_high,
            "invalidation_level": self.invalidation_level,
            "reason_codes": self.reason_codes,
            "edge_formula_version": self.edge_formula_version,
        }


def path_quality(median_path: list[float], last_close: float) -> float:
    """0..1 score: directional consistency + linearity of the median path."""
    arr = np.asarray(median_path, dtype=float)
    if arr.size < 3:
        return 0.0
    steps = np.diff(arr)
    total = arr[-1] - last_close
    if abs(total) < 1e-12:
        return 0.0
    directional_consistency = float(np.mean(np.sign(steps) == np.sign(total)))

    # R^2 of a straight-line fit (smooth trend -> high)
    x = np.arange(arr.size)
    slope, intercept = np.polyfit(x, arr, 1)
    fit = slope * x + intercept
    ss_res = float(np.sum((arr - fit) ** 2))
    ss_tot = float(np.sum((arr - arr.mean()) ** 2)) + 1e-12
    r2 = max(0.0, 1.0 - ss_res / ss_tot)

    return float(np.clip(0.5 * directional_consistency + 0.5 * r2, 0.0, 1.0))


def _confidence(p: float, bands) -> ConfidenceLabel:
    if p >= bands.high:
        return ConfidenceLabel.HIGH
    if p >= bands.medium:
        return ConfidenceLabel.MEDIUM
    if p >= bands.low:
        return ConfidenceLabel.LOW
    return ConfidenceLabel.NONE


def score_signal(
    *,
    forecast: ForecastDistribution,
    regime: RegimeResult,
    df: pd.DataFrame,
    strategy: StrategyConfig,
    risk: RiskConfig,
) -> SignalResult:
    """Produce a fully-scored, reason-coded signal for one asset."""
    eps = strategy.edge_weights.tiny_number
    p_up, p_down = forecast.p_up, forecast.p_down
    pq = path_quality(forecast.median_path, forecast.last_close)
    liq = ind.liquidity_score(df)
    round_trip_cost = 2.0 * (risk.fee_bps + risk.slippage_bps) / 10000.0

    reasons: list[str] = []
    explanations: list[dict] = []

    # --- choose direction from forecast probabilities ---
    if p_up >= strategy.minimum_p_up and p_up >= p_down:
        side = Side.LONG
    elif p_down >= strategy.minimum_p_down and p_down > p_up:
        side = Side.SHORT
    else:
        side = None

    if side is None:
        reasons.append(ReasonCode.PROBABILITY_BELOW_THRESHOLD.value)
        return _no_edge(forecast, regime, pq, liq, strategy, reasons)

    # --- structure (entry) evaluation ---
    structure = evaluate_structure(
        df, side, late_entry_atr_multiple=strategy.late_entry_atr_multiple
    )

    # --- directional + asymmetry + cost factors ---
    # Asymmetry measures reward-to-risk ratio for the chosen direction.
    # Capped at 100 to prevent numerical blow-up when all samples agree
    # on direction (denominator collapses to eps, inflating edge to millions).
    _MAX_ASYMMETRY = 100.0
    if side == Side.LONG:
        direction_score = p_up - 0.5
        asymmetry = min(
            max(forecast.q90_return, 0.0) / max(abs(forecast.q10_return), eps),
            _MAX_ASYMMETRY,
        )
        cost_adjusted_edge = forecast.median_return - round_trip_cost
        regime_aligned = regime.regime not in _BLOCK_LONG
        aligned_set = _ALIGNED_LONG
    else:
        direction_score = p_down - 0.5
        asymmetry = min(
            max(-forecast.q10_return, 0.0) / max(abs(forecast.q90_return), eps),
            _MAX_ASYMMETRY,
        )
        cost_adjusted_edge = (-forecast.median_return) - round_trip_cost
        regime_aligned = regime.regime not in _BLOCK_SHORT
        aligned_set = _ALIGNED_SHORT

    trend_alignment = (
        1.0 if regime.regime in aligned_set else (-1.0 if not regime_aligned else 0.0)
    )
    regime_factor = regime.regime_score if regime_aligned else 0.0

    # volatility penalty rises above the configured ratio threshold
    vr = forecast.forecast_volatility_ratio
    over = max(0.0, vr - strategy.edge_weights.volatility_penalty_threshold)
    volatility_penalty = strategy.edge_weights.volatility_penalty_scale * over

    edge_score = (
        direction_score * asymmetry * pq * max(regime_factor, eps) - volatility_penalty
    )

    confidence = _confidence(max(p_up, p_down), strategy.confidence_bands)

    # --- gating -> single status + reason codes (blocks take precedence) ---
    status = _gate(
        side=side,
        edge_score=edge_score,
        cost_adjusted_edge=cost_adjusted_edge,
        asymmetry=asymmetry,
        vr=vr,
        uncertainty=forecast.uncertainty_score,
        pq=pq,
        regime_aligned=regime_aligned,
        structure=structure,
        strategy=strategy,
        reasons=reasons,
    )

    explanations = _build_explanations(
        side, p_up, p_down, asymmetry, cost_adjusted_edge, vr, pq, regime, structure, strategy
    )

    return SignalResult(
        symbol=forecast.symbol,
        timeframe=forecast.timeframe,
        as_of=forecast.context_end,
        side=side,
        status=status,
        confidence_label=confidence,
        p_up=p_up,
        p_down=p_down,
        median_return=forecast.median_return,
        q10_return=forecast.q10_return,
        q90_return=forecast.q90_return,
        asymmetry_score=round(float(asymmetry), 4),
        forecast_volatility_ratio=round(vr, 4),
        path_quality=round(pq, 4),
        trend_alignment=trend_alignment,
        regime_score=round(regime.regime_score, 4),
        liquidity_score=round(liq, 4),
        cost_adjusted_edge=round(cost_adjusted_edge, 6),
        edge_score=round(float(edge_score), 6),
        entry_zone_low=structure.entry_zone_low,
        entry_zone_high=structure.entry_zone_high,
        invalidation_level=structure.invalidation_level,
        reason_codes=reasons,
        edge_formula_version=strategy.edge_formula_version,
        explanations=explanations,
    )


def _gate(
    *, side, edge_score, cost_adjusted_edge, asymmetry, vr, uncertainty, pq, regime_aligned,
    structure: StructureResult, strategy: StrategyConfig, reasons: list[str]
) -> TradeCandidateStatus:
    # 1. uncertainty / volatility
    if vr > strategy.maximum_volatility_ratio or uncertainty > 0.85:
        reasons.append(ReasonCode.VOLATILITY_TOO_HIGH.value)
        reasons.append(ReasonCode.UNCERTAINTY_TOO_HIGH.value)
        return TradeCandidateStatus.BLOCKED_BY_UNCERTAINTY

    # 2. regime conflict
    if strategy.require_regime_alignment and not regime_aligned:
        reasons.append(ReasonCode.REGIME_CONFLICT.value)
        return TradeCandidateStatus.BLOCKED_BY_REGIME

    # 3. costs
    if cost_adjusted_edge < strategy.minimum_cost_adjusted_edge:
        reasons.append(ReasonCode.COST_EXCEEDS_EDGE.value)
        return TradeCandidateStatus.BLOCKED_BY_COSTS

    # 4. late entry
    if structure.late_entry:
        reasons.append(ReasonCode.LATE_ENTRY.value)
        return TradeCandidateStatus.BLOCKED_BY_LATE_ENTRY

    # 5. asymmetry / path quality / structure -> watch if not all there
    if asymmetry < strategy.minimum_asymmetry:
        reasons.append(ReasonCode.ASYMMETRY_UNFAVORABLE.value)
        return TradeCandidateStatus.WATCH
    if pq < strategy.minimum_path_quality:
        reasons.append(ReasonCode.EDGE_BELOW_THRESHOLD.value)
        return TradeCandidateStatus.WATCH
    if strategy.require_market_structure_confirmation and not structure.confirmed:
        reasons.append(ReasonCode.NO_STRUCTURE_CONFIRMATION.value)
        return TradeCandidateStatus.WATCH
    if edge_score < strategy.minimum_edge_score:
        reasons.append(ReasonCode.EDGE_BELOW_THRESHOLD.value)
        return TradeCandidateStatus.WATCH

    # 6. confirmed candidate
    reasons.extend(
        [
            ReasonCode.EDGE_CONFIRMED.value,
            ReasonCode.REGIME_ALIGNED.value,
            ReasonCode.STRUCTURE_CONFIRMED.value,
            ReasonCode.ASYMMETRY_FAVORABLE.value,
        ]
    )
    return (
        TradeCandidateStatus.LONG_CANDIDATE
        if side == Side.LONG
        else TradeCandidateStatus.SHORT_CANDIDATE
    )


def _no_edge(forecast, regime, pq, liq, strategy, reasons) -> SignalResult:
    return SignalResult(
        symbol=forecast.symbol,
        timeframe=forecast.timeframe,
        as_of=forecast.context_end,
        side=None,
        status=TradeCandidateStatus.NO_EDGE,
        confidence_label=ConfidenceLabel.NONE,
        p_up=forecast.p_up,
        p_down=forecast.p_down,
        median_return=forecast.median_return,
        q10_return=forecast.q10_return,
        q90_return=forecast.q90_return,
        asymmetry_score=0.0,
        forecast_volatility_ratio=round(forecast.forecast_volatility_ratio, 4),
        path_quality=round(pq, 4),
        trend_alignment=0.0,
        regime_score=round(regime.regime_score, 4),
        liquidity_score=round(liq, 4),
        cost_adjusted_edge=0.0,
        edge_score=0.0,
        reason_codes=reasons,
        edge_formula_version=strategy.edge_formula_version,
    )


def _build_explanations(
    side, p_up, p_down, asymmetry, cost_edge, vr, pq, regime, structure, strategy
) -> list[dict]:
    p = p_up if side == Side.LONG else p_down
    return [
        {"factor": "probability", "value": round(p, 4), "threshold": strategy.minimum_p_up,
         "passed": p >= strategy.minimum_p_up,
         "text": f"P({side.value}) = {p:.2f}"},
        {"factor": "asymmetry", "value": round(float(asymmetry), 3),
         "threshold": strategy.minimum_asymmetry, "passed": asymmetry >= strategy.minimum_asymmetry,
         "text": f"Upside/downside asymmetry {asymmetry:.2f}"},
        {"factor": "cost_adjusted_edge", "value": round(cost_edge, 5),
         "threshold": strategy.minimum_cost_adjusted_edge,
         "passed": cost_edge >= strategy.minimum_cost_adjusted_edge,
         "text": f"Edge after fees+slippage {cost_edge:.3%}"},
        {"factor": "volatility_ratio", "value": round(vr, 3),
         "threshold": strategy.maximum_volatility_ratio, "passed": vr <= strategy.maximum_volatility_ratio,
         "text": f"Forecast vol {vr:.2f}x realized"},
        {"factor": "path_quality", "value": round(pq, 3), "threshold": strategy.minimum_path_quality,
         "passed": pq >= strategy.minimum_path_quality, "text": f"Path quality {pq:.2f}"},
        {"factor": "regime", "value": round(regime.regime_score, 3), "threshold": None,
         "passed": True, "text": regime.explanation},
        {"factor": "structure", "value": float(len(structure.conditions_met)), "threshold": 1.0,
         "passed": structure.confirmed,
         "text": f"Triggers: {', '.join(structure.conditions_met) or 'none'}"},
    ]
