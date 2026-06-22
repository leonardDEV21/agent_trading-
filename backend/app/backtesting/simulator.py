"""Event-driven single-symbol trade simulator (no lookahead).

Contract that guarantees no future leakage:
- A decision at candle ``i`` may only see ``df.iloc[:i+1]`` (candles that have
  CLOSED).
- The resulting entry executes at the OPEN of candle ``i+1``.
- Stop/TP exits are evaluated on later candles' high/low. When a single candle
  could hit both stop and target, the STOP is assumed first (worst case).

Fees and slippage are applied to every fill. Net PnL is always reported.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from app.backtesting.fee_model import fee_cost
from app.backtesting.slippage_model import apply_slippage
from app.config import RiskConfig
from app.core.constants import ReasonCode, Side
from app.risk.exposure_limits import assess_trade
from app.strategy import volatility_engine as ind


@dataclass
class TradePlan:
    side: Side
    atr: float
    invalidation_level: float | None
    forecast_target: float | None
    regime: str = "unknown"
    reason_codes: list[str] = field(default_factory=list)
    beta_group: str | None = None
    uncertainty: float = 0.0


PlanFn = Callable[[pd.DataFrame], TradePlan | None]


def simulate(
    df: pd.DataFrame,
    *,
    symbol: str,
    plan_fn: PlanFn,
    risk: RiskConfig,
    warmup: int,
    decision_frequency: int = 1,
    max_hold_candles: int = 24,
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
    slippage_model: str = "fixed_bps",
    initial_equity: float = 10000.0,
) -> tuple[list[dict], list[tuple[datetime, float]]]:
    trades: list[dict] = []
    equity_curve: list[tuple[datetime, float]] = []
    equity = initial_equity

    idx = df.index
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    ema200 = ind.ema(df["close"], 200).to_numpy(float)

    pending: TradePlan | None = None
    pos: dict | None = None
    consecutive_losses = 0
    day_pnl: dict[str, float] = {}

    for i in range(warmup, len(df)):
        ts = idx[i].to_pydatetime()
        day = ts.strftime("%Y-%m-%d")

        # 1. execute a pending entry at this candle's open
        if pending is not None and pos is None:
            entry_fill = apply_slippage(
                o[i], pending.side, model=slippage_model, slippage_bps=slippage_bps,
                atr=pending.atr,
            )
            decision = assess_trade(
                side=pending.side, entry=entry_fill, atr=pending.atr,
                invalidation_level=pending.invalidation_level,
                forecast_target=pending.forecast_target, beta_group=pending.beta_group,
                open_positions=[], daily_pnl_pct=day_pnl.get(day, 0.0) / initial_equity,
                kill_switch_active=consecutive_losses >= risk.kill_switch.max_consecutive_losses_per_day,
                risk=risk,
            )
            if decision.allowed:
                entry_fee = fee_cost(decision.size * entry_fill, fee_bps)
                pos = {
                    "side": pending.side, "entry_price": entry_fill, "ideal_entry": o[i],
                    "stop": decision.stop, "tp": decision.take_profit, "size": decision.size,
                    "risk_amount": decision.risk_amount, "entry_time": ts, "entry_index": i,
                    "entry_fee": entry_fee, "regime": pending.regime,
                    "reason_codes": pending.reason_codes + decision.reason_codes,
                }
            pending = None

        # 2. manage exit on this candle
        if pos is not None:
            hold = i - pos["entry_index"]
            exit_price = None
            reason = None
            side = pos["side"]

            if side == Side.LONG:
                if low[i] <= pos["stop"]:
                    exit_price, reason = pos["stop"], ReasonCode.EXIT_STOP_LOSS
                elif pos["tp"] is not None and h[i] >= pos["tp"]:
                    exit_price, reason = pos["tp"], ReasonCode.EXIT_TAKE_PROFIT
                elif c[i] < ema200[i] and hold >= 1:
                    exit_price, reason = c[i], ReasonCode.EXIT_REGIME_FLIP
            else:
                if h[i] >= pos["stop"]:
                    exit_price, reason = pos["stop"], ReasonCode.EXIT_STOP_LOSS
                elif pos["tp"] is not None and low[i] <= pos["tp"]:
                    exit_price, reason = pos["tp"], ReasonCode.EXIT_TAKE_PROFIT
                elif c[i] > ema200[i] and hold >= 1:
                    exit_price, reason = c[i], ReasonCode.EXIT_REGIME_FLIP

            if exit_price is None and hold >= max_hold_candles:
                exit_price, reason = c[i], ReasonCode.EXIT_MAX_HOLD

            if exit_price is not None:
                exit_fill = apply_slippage(
                    exit_price, Side.SHORT if side == Side.LONG else Side.LONG,
                    model=slippage_model, slippage_bps=slippage_bps, atr=pos.get("atr", 0.0) or 0.0,
                )
                size = pos["size"]
                direction = 1 if side == Side.LONG else -1
                gross = (exit_fill - pos["entry_price"]) * size * direction
                exit_fee = fee_cost(size * exit_fill, fee_bps)
                fees = pos["entry_fee"] + exit_fee
                slip = (abs(pos["entry_price"] - pos["ideal_entry"]) + abs(exit_fill - exit_price)) * size
                net = gross - fees
                equity += net
                day_pnl[day] = day_pnl.get(day, 0.0) + net
                consecutive_losses = consecutive_losses + 1 if net < 0 else 0

                trades.append(
                    {
                        "symbol": symbol, "side": side.value, "entry_time": pos["entry_time"],
                        "entry_price": pos["entry_price"], "exit_time": ts, "exit_price": exit_fill,
                        "stop_loss": pos["stop"], "take_profit": pos["tp"], "size": size,
                        "risk_amount": pos["risk_amount"], "gross_pnl": round(gross, 6),
                        "fees": round(fees, 6), "slippage": round(slip, 6), "net_pnl": round(net, 6),
                        "regime": pos["regime"], "exit_reason": reason.value if reason else None,
                        "reason_codes": pos["reason_codes"],
                    }
                )
                pos = None

        # 3. make a new decision (flat, no pending, on cadence)
        if pos is None and pending is None and (i % max(decision_frequency, 1) == 0):
            plan = plan_fn(df.iloc[: i + 1])
            if plan is not None:
                pending = plan

        # 4. equity point (realized + mark-to-market of any open position)
        mtm = equity
        if pos is not None:
            direction = 1 if pos["side"] == Side.LONG else -1
            mtm += (c[i] - pos["entry_price"]) * pos["size"] * direction
        equity_curve.append((ts, round(mtm, 4)))

    return trades, equity_curve
