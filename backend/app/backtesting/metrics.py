"""Performance metrics. All returns are NET of fees and slippage.

A trade dict is expected to have at least: net_pnl, gross_pnl, fees, slippage,
entry_time, exit_time, regime, symbol, side.
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np

from app.core.timeframes import annualization_periods


def _safe_div(a: float, b: float) -> float:
    return a / b if b not in (0, 0.0) else 0.0


def compute_metrics(
    trades: list[dict],
    equity_curve: list[tuple[datetime, float]],
    *,
    initial_equity: float,
    timeframe: str,
) -> dict:
    n = len(trades)
    net_pnls = [t.get("net_pnl", 0.0) or 0.0 for t in trades]
    wins = [p for p in net_pnls if p > 0]
    losses = [p for p in net_pnls if p < 0]

    total_net = float(sum(net_pnls))
    final_equity = initial_equity + total_net
    total_return = _safe_div(final_equity - initial_equity, initial_equity)

    gross_profit = float(sum(wins))
    gross_loss = float(abs(sum(losses)))
    profit_factor = _safe_div(gross_profit, gross_loss)
    win_rate = _safe_div(len(wins), n)
    avg_win = _safe_div(gross_profit, len(wins))
    avg_loss = _safe_div(gross_loss, len(losses))
    expectancy = _safe_div(total_net, n)

    fee_cost = float(sum(t.get("fees", 0.0) or 0.0 for t in trades))
    slippage_cost = float(sum(t.get("slippage", 0.0) or 0.0 for t in trades))

    # equity-based metrics
    eq = np.array([e for _, e in equity_curve], dtype=float) if equity_curve else np.array([initial_equity])
    max_dd, longest_dd = _drawdown(eq)
    sharpe, sortino = _risk_adjusted(eq, timeframe)

    hold_times = [
        (t["exit_time"] - t["entry_time"]).total_seconds() / 3600.0
        for t in trades
        if t.get("exit_time") and t.get("entry_time")
    ]
    avg_hold_hours = float(np.mean(hold_times)) if hold_times else 0.0

    return {
        "num_trades": n,
        "total_return": round(total_return, 6),
        "final_equity": round(final_equity, 2),
        "net_pnl": round(total_net, 2),
        "win_rate": round(win_rate, 4),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "expectancy": round(expectancy, 4),
        "profit_factor": round(profit_factor, 4),
        "sharpe": round(sharpe, 4),
        "sortino": round(sortino, 4),
        "max_drawdown": round(max_dd, 6),
        "longest_drawdown_periods": longest_dd,
        "avg_hold_hours": round(avg_hold_hours, 2),
        "fee_cost": round(fee_cost, 2),
        "slippage_cost": round(slippage_cost, 2),
        "best_trade": round(max(net_pnls), 2) if net_pnls else 0.0,
        "worst_trade": round(min(net_pnls), 2) if net_pnls else 0.0,
        "gross_pnl": round(float(sum(t.get("gross_pnl", 0.0) or 0.0 for t in trades)), 2),
        "by_regime": _breakdown(trades, "regime"),
        "by_symbol": _breakdown(trades, "symbol"),
        "costs_included": True,
    }


def _drawdown(equity: np.ndarray) -> tuple[float, int]:
    if equity.size == 0:
        return 0.0, 0
    running_max = np.maximum.accumulate(equity)
    dd = (equity - running_max) / running_max
    max_dd = float(dd.min()) if dd.size else 0.0

    longest = cur = 0
    for x in dd:
        if x < 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    return max_dd, longest


def _risk_adjusted(equity: np.ndarray, timeframe: str) -> tuple[float, float]:
    if equity.size < 3:
        return 0.0, 0.0
    rets = np.diff(equity) / equity[:-1]
    if rets.std() == 0:
        return 0.0, 0.0
    periods = annualization_periods(timeframe)
    ann = math.sqrt(periods)
    sharpe = float(rets.mean() / rets.std() * ann)
    downside = rets[rets < 0]
    sortino = float(rets.mean() / downside.std() * ann) if downside.size and downside.std() > 0 else 0.0
    return sharpe, sortino


def _breakdown(trades: list[dict], key: str) -> dict:
    out: dict[str, dict] = {}
    for t in trades:
        k = t.get(key) or "unknown"
        b = out.setdefault(k, {"trades": 0, "net_pnl": 0.0, "wins": 0})
        b["trades"] += 1
        b["net_pnl"] += t.get("net_pnl", 0.0) or 0.0
        if (t.get("net_pnl") or 0.0) > 0:
            b["wins"] += 1
    for b in out.values():
        b["net_pnl"] = round(b["net_pnl"], 2)
        b["win_rate"] = round(_safe_div(b["wins"], b["trades"]), 4)
    return out
