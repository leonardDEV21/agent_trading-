"""Baseline strategies the Kronos strategy must beat (after costs).

Compared primarily on risk-adjusted metrics (Sharpe, profit factor, max
drawdown) since position sizing differs from the risk-based Kronos sizing.
A Kronos strategy that cannot beat these is not a real edge (BACKTEST_SPEC.md).
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from app.backtesting.fee_model import fee_cost
from app.backtesting.slippage_model import fixed_bps_slippage_price
from app.core.constants import Side
from app.strategy import volatility_engine as ind


def _simulate_long_only(
    df: pd.DataFrame,
    target_long: pd.Series,
    *,
    symbol: str,
    fee_bps: float,
    slippage_bps: float,
    initial_equity: float,
) -> tuple[list[dict], list[tuple[datetime, float]]]:
    """Simulate a long/flat strategy from a desired-exposure boolean series.

    Enters/exits at the NEXT candle open (no same-bar lookahead). Full-equity
    notional. Returns (trades, equity_curve).
    """
    trades: list[dict] = []
    equity = initial_equity
    equity_curve: list[tuple[datetime, float]] = []

    in_pos = False
    entry_price = 0.0
    size = 0.0
    entry_time: datetime | None = None
    entry_fee = 0.0

    opens = df["open"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    idx = df.index
    want = target_long.to_numpy()

    for i in range(len(df) - 1):
        nxt_open = opens[i + 1]
        # manage transitions at next open
        if not in_pos and want[i]:
            fill = fixed_bps_slippage_price(nxt_open, Side.LONG, slippage_bps)
            size = equity / fill
            entry_price = fill
            entry_time = idx[i + 1].to_pydatetime()
            entry_fee = fee_cost(size * fill, fee_bps)
            in_pos = True
        elif in_pos and not want[i]:
            fill = fixed_bps_slippage_price(nxt_open, Side.SHORT, slippage_bps)
            exit_fee = fee_cost(size * fill, fee_bps)
            gross = (fill - entry_price) * size
            fees = entry_fee + exit_fee
            slip = abs(fill - nxt_open) * size + abs(entry_price - opens[i]) * 0  # exit slip
            net = gross - fees
            equity += net
            trades.append(
                {
                    "symbol": symbol, "side": "long", "entry_time": entry_time,
                    "exit_time": idx[i + 1].to_pydatetime(), "gross_pnl": gross,
                    "fees": fees, "slippage": slip, "net_pnl": net, "regime": "baseline",
                }
            )
            in_pos = False

        # mark-to-market equity
        mtm = equity + ((closes[i + 1] - entry_price) * size if in_pos else 0.0)
        equity_curve.append((idx[i + 1].to_pydatetime(), mtm))

    return trades, equity_curve


def buy_and_hold(df, symbol, *, fee_bps, slippage_bps, initial_equity):
    want = pd.Series(True, index=df.index)
    return _simulate_long_only(df, want, symbol=symbol, fee_bps=fee_bps,
                               slippage_bps=slippage_bps, initial_equity=initial_equity)


def ema_trend(df, symbol, *, fee_bps, slippage_bps, initial_equity, fast=50, slow=200):
    ef, es = ind.ema(df["close"], fast), ind.ema(df["close"], slow)
    want = (ef > es).fillna(False)
    return _simulate_long_only(df, want, symbol=symbol, fee_bps=fee_bps,
                               slippage_bps=slippage_bps, initial_equity=initial_equity)


def atr_breakout(df, symbol, *, fee_bps, slippage_bps, initial_equity, lookback=20):
    high_n = df["high"].rolling(lookback).max().shift(1)
    low_n = df["low"].rolling(lookback).min().shift(1)
    raw = pd.Series(np.nan, index=df.index)
    raw[df["close"] > high_n] = 1.0
    raw[df["close"] < low_n] = 0.0
    want = raw.ffill().fillna(0.0).astype(bool)
    return _simulate_long_only(df, want, symbol=symbol, fee_bps=fee_bps,
                               slippage_bps=slippage_bps, initial_equity=initial_equity)


def random_entry(df, symbol, *, fee_bps, slippage_bps, initial_equity, avg_hold=24, seed=42):
    rng = np.random.default_rng(seed)
    n = len(df)
    want = np.zeros(n, dtype=bool)
    i = 0
    p_enter = 1.0 / max(avg_hold, 1)
    while i < n:
        if rng.random() < p_enter:
            hold = max(1, int(rng.poisson(avg_hold)))
            want[i:i + hold] = True
            i += hold
        else:
            i += 1
    return _simulate_long_only(
        df, pd.Series(want, index=df.index), symbol=symbol, fee_bps=fee_bps,
        slippage_bps=slippage_bps, initial_equity=initial_equity
    )


BASELINES = {
    "buy_and_hold": buy_and_hold,
    "ema_trend": ema_trend,
    "atr_breakout": atr_breakout,
    "random_entry": random_entry,
}
