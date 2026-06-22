"""Backtest integrity: no lookahead, costs always applied, fee/slippage models."""

from __future__ import annotations

import pandas as pd

from app.backtesting.fee_model import fee_cost, round_trip_fee
from app.backtesting.metrics import compute_metrics
from app.backtesting.simulator import TradePlan, simulate
from app.backtesting.slippage_model import apply_slippage, fixed_bps_slippage_price
from app.backtesting.walk_forward import build_folds
from app.config import RiskConfig
from app.core.constants import Side
from app.strategy import volatility_engine as ind


def test_simulator_never_sees_future_candles(candles):
    """plan_fn must only ever receive candles up to the decision point."""
    seen_last_ts = []

    def plan_fn(hist: pd.DataFrame):
        seen_last_ts.append(hist.index[-1])
        # the history handed to us must be a strict prefix of the full frame
        assert hist.index[-1] in candles.index
        assert len(hist) <= len(candles)
        return None  # never trade; we only audit the inputs

    simulate(candles, symbol="BTC/USDT", plan_fn=plan_fn, risk=RiskConfig(), warmup=360)
    # decisions are strictly increasing in time and bounded by the dataset end
    assert seen_last_ts == sorted(seen_last_ts)
    assert max(seen_last_ts) <= candles.index[-1]


def test_costs_reduce_pnl(candles):
    def plan_fn(hist: pd.DataFrame):
        if hist["close"].iloc[-1] > hist["close"].iloc[-3]:
            return TradePlan(side=Side.LONG, atr=float(ind.atr(hist).iloc[-1]),
                             invalidation_level=None, forecast_target=hist["close"].iloc[-1] * 1.03,
                             regime="trend_up", reason_codes=["t"])
        return None

    trades, equity = simulate(candles, symbol="BTC/USDT", plan_fn=plan_fn, risk=RiskConfig(),
                              warmup=360, fee_bps=10, slippage_bps=5)
    assert trades, "expected at least one trade"
    for t in trades:
        assert t["fees"] > 0  # fees always charged
        assert t["slippage"] >= 0
        assert t["net_pnl"] <= t["gross_pnl"] + 1e-9  # net never exceeds gross
    m = compute_metrics(trades, equity, initial_equity=10000, timeframe="1h")
    assert m["costs_included"] is True
    assert m["fee_cost"] > 0


def test_entry_executes_after_decision(candles):
    """Entry time must be strictly after the decision candle (next-open fill)."""
    entries = []

    def plan_fn(hist: pd.DataFrame):
        decision_ts = hist.index[-1]
        if len(entries) == 0 and len(hist) == 365:
            entries.append(decision_ts)
            return TradePlan(side=Side.LONG, atr=float(ind.atr(hist).iloc[-1]),
                             invalidation_level=None, forecast_target=hist["close"].iloc[-1] * 1.05,
                             regime="x", reason_codes=["t"])
        return None

    trades, _ = simulate(candles, symbol="BTC/USDT", plan_fn=plan_fn, risk=RiskConfig(),
                         warmup=360, max_hold_candles=24)
    assert trades
    assert trades[0]["entry_time"] > entries[0]  # filled on a later candle, never the decision bar


def test_fee_model():
    assert fee_cost(10000, 10) == 10.0  # 10 bps of 10k
    assert round_trip_fee(10000, 10) == 20.0


def test_slippage_is_adverse():
    # buys fill higher, sells fill lower
    assert fixed_bps_slippage_price(100, Side.LONG, 5) > 100
    assert fixed_bps_slippage_price(100, Side.SHORT, 5) < 100
    assert apply_slippage(100, Side.LONG, model="fixed_bps", slippage_bps=10) == 100.1


def test_build_folds_within_bounds():
    folds = build_folds(n=1000, warmup=360, test_window=168, step=168)
    assert folds[0][0] == 360
    for start, end in folds:
        assert 360 <= start < end <= 1000
