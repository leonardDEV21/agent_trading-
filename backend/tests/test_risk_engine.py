"""Risk engine: sizing, stops, take-profit, exposure limits, kill switch."""

from __future__ import annotations

from app.config import RiskConfig
from app.core.constants import ReasonCode, Side, TradeCandidateStatus
from app.risk.exposure_limits import OpenPositionView, assess_trade, correlated_count
from app.risk.kill_switch import (
    exceeds_consecutive_losses,
    exceeds_spread,
    exceeds_uncertainty,
)
from app.risk.position_sizing import size_position
from app.risk.stop_engine import compute_stop
from app.risk.take_profit_engine import compute_take_profit, reward_risk_ratio


def test_position_size_matches_risk_budget():
    r = size_position(side=Side.LONG, account_size=10000, risk_per_trade=0.005,
                      entry=100.0, stop=98.0, allow_leverage=False)
    # risk budget = 50; stop distance = 2 => size ~ 25, but notional 2500 < account so uncapped
    assert r.valid
    assert abs(r.risk_amount - 50.0) < 1e-6
    assert abs(r.size - 25.0) < 1e-6


def test_no_leverage_caps_notional():
    # very tight stop would imply huge size; without leverage, notional capped at account
    r = size_position(side=Side.LONG, account_size=10000, risk_per_trade=0.5,
                      entry=100.0, stop=99.99, allow_leverage=False)
    assert r.notional <= 10000 + 1e-6
    assert ReasonCode.RISK_LEVERAGE_DISABLED.value in r.reason_codes


def test_zero_stop_distance_invalid():
    r = size_position(side=Side.LONG, account_size=10000, risk_per_trade=0.005,
                      entry=100.0, stop=100.0)
    assert not r.valid
    assert ReasonCode.RISK_NO_STOP.value in r.reason_codes


def test_stop_is_on_correct_side():
    long_stop = compute_stop(side=Side.LONG, entry=100, atr=2, min_stop_distance_pct=0.003)
    short_stop = compute_stop(side=Side.SHORT, entry=100, atr=2, min_stop_distance_pct=0.003)
    assert long_stop < 100 < short_stop


def test_stop_respects_minimum_distance():
    stop = compute_stop(side=Side.LONG, entry=100, atr=0.0001, min_stop_distance_pct=0.01)
    assert 100 - stop >= 100 * 0.01 - 1e-9


def test_take_profit_respects_min_rr():
    tp = compute_take_profit(side=Side.LONG, entry=100, stop=98, min_reward_risk_ratio=2.0)
    assert reward_risk_ratio(Side.LONG, 100, 98, tp) >= 2.0 - 1e-9


def test_correlated_count():
    pos = [OpenPositionView("ETH/USDT", "btc_beta"), OpenPositionView("SOL/USDT", "btc_beta")]
    assert correlated_count(pos, "btc_beta") == 2
    assert correlated_count(pos, "us_equity") == 0


def test_assess_trade_blocks_on_kill_switch():
    d = assess_trade(side=Side.LONG, entry=100, atr=2, invalidation_level=None,
                     forecast_target=110, beta_group="btc_beta", open_positions=[],
                     daily_pnl_pct=0.0, kill_switch_active=True, risk=RiskConfig())
    assert not d.allowed
    assert d.status == TradeCandidateStatus.BLOCKED_BY_RISK
    assert ReasonCode.RISK_KILL_SWITCH_ACTIVE.value in d.reason_codes


def test_assess_trade_blocks_on_max_open_positions():
    risk = RiskConfig(max_open_positions=1)
    d = assess_trade(side=Side.LONG, entry=100, atr=2, invalidation_level=None,
                     forecast_target=110, beta_group="x",
                     open_positions=[OpenPositionView("ETH/USDT", "y")],
                     daily_pnl_pct=0.0, kill_switch_active=False, risk=risk)
    assert not d.allowed
    assert ReasonCode.RISK_MAX_OPEN_POSITIONS.value in d.reason_codes


def test_assess_trade_blocks_on_daily_loss():
    risk = RiskConfig(max_daily_loss=0.015)
    d = assess_trade(side=Side.LONG, entry=100, atr=2, invalidation_level=None,
                     forecast_target=110, beta_group="x", open_positions=[],
                     daily_pnl_pct=-0.02, kill_switch_active=False, risk=risk)
    assert not d.allowed
    assert ReasonCode.RISK_DAILY_LOSS_LIMIT.value in d.reason_codes


def test_assess_trade_allows_clean_setup():
    d = assess_trade(side=Side.LONG, entry=100, atr=2, invalidation_level=96,
                     forecast_target=108, beta_group="btc_beta", open_positions=[],
                     daily_pnl_pct=0.0, kill_switch_active=False, risk=RiskConfig())
    assert d.allowed
    assert d.stop is not None and d.stop < 100
    assert d.take_profit is not None and d.take_profit > 100
    assert d.size > 0


def test_kill_switch_predicates():
    assert exceeds_consecutive_losses(2, 2)
    assert not exceeds_consecutive_losses(1, 2)
    assert exceeds_uncertainty(0.9, 0.85)
    assert exceeds_spread(30, 25)
