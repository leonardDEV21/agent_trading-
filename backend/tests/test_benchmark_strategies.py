"""Baselines must book PnL even when they never signal an exit (the buy_and_hold bug)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.backtesting import benchmark_strategies as bs


def _rising_df(n=200, start=100.0, step=0.5):
    close = np.array([start + step * i for i in range(n)], dtype=float)
    idx = pd.date_range("2025-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "volume": np.ones(n)}, index=idx)


def test_buy_and_hold_books_a_trade_and_positive_return_on_uptrend():
    df = _rising_df()
    trades, curve = bs.buy_and_hold(df, "ETH/USDT", fee_bps=10, slippage_bps=5,
                                    initial_equity=10_000)
    assert len(trades) == 1, "buy_and_hold must book exactly one (forced final) trade"
    t = trades[0]
    assert t["net_pnl"] > 0  # held through a clear uptrend → positive after fees
    # entry ~first open (next-bar fill), exit at last close → captures the run-up
    assert t["exit_time"] == df.index[-1].to_pydatetime()
    assert len(curve) > 0


def test_buy_and_hold_flat_market_is_only_fees():
    n = 200
    close = np.full(n, 100.0)
    idx = pd.date_range("2025-01-01", periods=n, freq="1h", tz="UTC")
    df = pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                       "volume": np.ones(n)}, index=idx)
    trades, _ = bs.buy_and_hold(df, "ETH/USDT", fee_bps=10, slippage_bps=5,
                                initial_equity=10_000)
    assert len(trades) == 1
    assert trades[0]["net_pnl"] < 0  # flat price, round-trip fees → small loss
