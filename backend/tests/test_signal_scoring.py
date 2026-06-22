"""Signal scoring: edge formula, statuses, reason codes, path quality."""

from __future__ import annotations

from datetime import datetime, timezone

from app.config import RiskConfig, StrategyConfig
from app.core.constants import ConfidenceLabel, ForecastMode, Regime, Side, TradeCandidateStatus
from app.kronos.forecast_postprocessor import ForecastDistribution
from app.strategy.regime_detector import RegimeResult
from app.strategy.signal_scoring import path_quality, score_signal

UTC = timezone.utc


def _forecast(last_close=100.0, p_up=0.7, p_down=0.3, median_return=0.02, q10=-0.01, q90=0.05,
              vol_ratio=1.0, uncertainty=0.2, median_path=None):
    if median_path is None:
        median_path = [last_close * (1 + median_return * (i + 1) / 24) for i in range(24)]
    return ForecastDistribution(
        symbol="BTC/USDT", timeframe="1h", created_at=datetime.now(UTC),
        context_start=datetime(2025, 1, 1, tzinfo=UTC), context_end=datetime(2025, 1, 15, tzinfo=UTC),
        horizon=24, sample_count=30, mode=ForecastMode.MOCK, model_name="mock-gbm-v1",
        model_config_hash="abc", last_close=last_close, median_path=median_path,
        q10_path=[last_close] * 24, q25_path=[last_close] * 24, q75_path=[last_close] * 24,
        q90_path=[last_close] * 24, p_up=p_up, p_down=p_down, median_return=median_return,
        q10_return=q10, q25_return=q10 / 2, q75_return=q90 / 2, q90_return=q90,
        forecast_volatility=0.01, forecast_volatility_ratio=vol_ratio, uncertainty_score=uncertainty,
    )


def _regime(regime=Regime.TREND_UP, score=0.8):
    return RegimeResult(symbol="BTC/USDT", timeframe="1h", as_of=datetime.now(UTC),
                        regime=regime, regime_score=score, market_regime=None, explanation="test")


def test_path_quality_high_for_clean_trend():
    up = [100 + i for i in range(24)]
    assert path_quality(up, 100.0) > 0.8


def test_path_quality_zero_for_flat():
    assert path_quality([100.0] * 24, 100.0) == 0.0


def test_no_edge_when_probabilities_neutral(candles):
    f = _forecast(p_up=0.5, p_down=0.5)
    sig = score_signal(forecast=f, regime=_regime(), df=candles,
                       strategy=StrategyConfig(), risk=RiskConfig())
    assert sig.status == TradeCandidateStatus.NO_EDGE
    assert sig.side is None
    assert "probability_below_threshold" in sig.reason_codes


def test_blocked_by_uncertainty(candles):
    f = _forecast(vol_ratio=5.0, uncertainty=0.95)
    sig = score_signal(forecast=f, regime=_regime(), df=candles,
                       strategy=StrategyConfig(), risk=RiskConfig())
    assert sig.status == TradeCandidateStatus.BLOCKED_BY_UNCERTAINTY
    assert "volatility_too_high" in sig.reason_codes


def test_blocked_by_costs_when_edge_below_fees(candles):
    f = _forecast(p_up=0.7, median_return=0.0001, q90=0.02, q10=-0.001)
    strat = StrategyConfig(minimum_cost_adjusted_edge=0.01)
    sig = score_signal(forecast=f, regime=_regime(), df=candles, strategy=strat, risk=RiskConfig())
    assert sig.status == TradeCandidateStatus.BLOCKED_BY_COSTS
    assert "cost_exceeds_edge" in sig.reason_codes


def test_blocked_by_regime_conflict(candles):
    f = _forecast(p_up=0.7)
    sig = score_signal(forecast=f, regime=_regime(Regime.TREND_DOWN, 0.8), df=candles,
                       strategy=StrategyConfig(), risk=RiskConfig())
    assert sig.status == TradeCandidateStatus.BLOCKED_BY_REGIME
    assert "regime_conflict" in sig.reason_codes


def test_long_candidate_when_all_pass(candles):
    f = _forecast(p_up=0.72, median_return=0.03, q90=0.06, q10=-0.01, vol_ratio=1.0)
    # disable structure confirmation and effectively disable the late-entry guard so we
    # isolate the "all gates pass" path
    strat = StrategyConfig(require_market_structure_confirmation=False, minimum_edge_score=0.0,
                           late_entry_atr_multiple=1000.0)
    sig = score_signal(forecast=f, regime=_regime(Regime.TREND_UP, 0.9), df=candles,
                       strategy=strat, risk=RiskConfig())
    assert sig.status == TradeCandidateStatus.LONG_CANDIDATE
    assert sig.side == Side.LONG
    assert "edge_confirmed" in sig.reason_codes
    assert sig.confidence_label in (ConfidenceLabel.HIGH, ConfidenceLabel.MEDIUM)


def test_every_signal_has_reason_codes(candles):
    for p in (0.5, 0.6, 0.72):
        sig = score_signal(forecast=_forecast(p_up=p, p_down=1 - p), regime=_regime(),
                           df=candles, strategy=StrategyConfig(), risk=RiskConfig())
        assert sig.reason_codes, "a signal must never be emitted without a reason code"
