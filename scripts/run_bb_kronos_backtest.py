#!/usr/bin/env python
"""Gated BB+Kronos walk-forward backtest.

Runs the two BB+Kronos setups (squeeze breakout, mean-reversion fade) ONLY if the
spread-validation premise passed (spread_validation.json from signal_eval.py). If the
premise failed, it refuses to run — by design: we do not build a strategy on a model
that cannot forecast move size. Hard stops remain enforced by the risk engine.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ.setdefault("KAT_ENABLE_SCHEDULER", "false")

from app.backtesting.benchmark_strategies import BASELINES  # noqa: E402
from app.backtesting.metrics import compute_metrics  # noqa: E402
from app.backtesting.simulator import simulate  # noqa: E402
from app.backtesting.walk_forward import build_folds  # noqa: E402
from app.config import get_config_store  # noqa: E402
from app.db.session import new_session  # noqa: E402
from app.kronos.adapter import KronosAdapter  # noqa: E402
from app.repositories import candles_repo  # noqa: E402
from app.strategy.bb_kronos import PLANS, BBKronosParams  # noqa: E402

VERDICT = os.environ.get("VERDICT_OUT", "/workspace/spread_validation.json")
KEEP = ["num_trades", "total_return", "net_pnl", "gross_pnl", "win_rate",
        "profit_factor", "sharpe", "max_drawdown", "fee_cost"]


def gate() -> bool:
    p = Path(VERDICT)
    if not p.exists():
        print(f"GATE: {VERDICT} missing — run signal_eval.py first. ABORT.")
        return False
    v = json.loads(p.read_text())
    print("spread validation verdict:", json.dumps(v))
    if not v.get("passed"):
        print("GATE FAILED — Kronos cannot forecast move size (spread IC below threshold).")
        print("NOT running BB+Kronos. This is the correct outcome, not an error.")
        return False
    print("GATE PASSED — volatility premise holds; running BB+Kronos backtests.\n")
    return True


def run_strategy(plan, candles_by_symbol, adapter, bt, risk, kronos) -> dict:
    params = BBKronosParams()
    warmup = max(bt.warmup_candles, kronos.context_length)
    all_trades: list[dict] = []
    for sym, df in candles_by_symbol.items():
        def plan_fn(hist, _sym=sym):
            try:
                fc = adapter.forecast(hist, symbol=_sym, timeframe=bt.timeframe)
            except Exception:
                return None
            return plan(fc, hist, params)

        for s, e in build_folds(len(df), warmup, bt.test_window_candles, bt.step_candles):
            ss = max(0, s - warmup)
            trades, eq = simulate(
                df.iloc[ss:e], symbol=sym, plan_fn=plan_fn, risk=risk, warmup=s - ss,
                decision_frequency=bt.decision_frequency_candles, max_hold_candles=bt.max_hold_candles,
                fee_bps=bt.fee_bps, slippage_bps=bt.slippage_bps, slippage_model=bt.slippage_model,
                initial_equity=bt.initial_equity,
            )
            all_trades.extend(trades)
    all_trades.sort(key=lambda t: t["exit_time"])
    equity = bt.initial_equity
    curve = []
    for t in all_trades:
        equity += t["net_pnl"]
        curve.append((t["exit_time"], equity))
    return compute_metrics(all_trades, curve, initial_equity=bt.initial_equity, timeframe=bt.timeframe)


def buy_and_hold(candles_by_symbol, bt, warmup) -> dict:
    fn = BASELINES.get("buy_and_hold")
    agg = []
    for sym, df in candles_by_symbol.items():
        sub = df.iloc[warmup:]
        if len(sub) < 3:
            continue
        trades, _ = fn(sub, sym, fee_bps=bt.fee_bps, slippage_bps=bt.slippage_bps,
                       initial_equity=bt.initial_equity)
        agg.extend(trades)
    agg.sort(key=lambda t: t["exit_time"])
    eq = bt.initial_equity
    curve = []
    for t in agg:
        eq += t["net_pnl"]
        curve.append((t["exit_time"], eq))
    return compute_metrics(agg, curve, initial_equity=bt.initial_equity, timeframe=bt.timeframe)


def main() -> None:
    if not gate():
        return
    store = get_config_store()
    bt, risk, kronos = store.backtest(), store.risk(), store.kronos()
    db = new_session()
    candles_by_symbol = {}
    for sym in bt.symbols:
        rows = candles_repo.get_candles(db, sym, bt.timeframe, ascending=True, limit=20000)
        if len(rows) >= bt.warmup_candles + bt.test_window_candles:
            candles_by_symbol[sym] = candles_repo.candles_to_df(rows)
    adapter = KronosAdapter(kronos)
    warmup = max(bt.warmup_candles, kronos.context_length)

    bh = buy_and_hold(candles_by_symbol, bt, warmup)
    print(f"BASELINE buy_and_hold: return={bh.get('total_return'):.3%} "
          f"sharpe={bh.get('sharpe')} pf={bh.get('profit_factor')}\n")

    for name, plan in PLANS.items():
        m = run_strategy(plan, candles_by_symbol, adapter, bt, risk, kronos)
        print(f"=== {name} ===")
        print(json.dumps({k: m[k] for k in KEEP if k in m}, indent=2, default=str))
        beats = (m.get("sharpe", -9) > bh.get("sharpe", 0)
                 and m.get("profit_factor", 0) > bh.get("profit_factor", 0))
        print(f"beats buy_and_hold (sharpe & pf): {beats}\n")
    db.close()


if __name__ == "__main__":
    main()
