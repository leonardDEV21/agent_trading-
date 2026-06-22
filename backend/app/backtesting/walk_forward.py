"""Walk-forward backtesting orchestrator.

For each symbol the candle history is split into rolling out-of-sample folds.
Within a fold, decisions are taken only on candles inside the test window and
may only see candles up to the decision point (the simulator enforces this).
Equity is threaded across folds. Baselines are run over the same decision range
so the Kronos strategy can be judged "real only if it beats them after costs".
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.backtesting.benchmark_strategies import BASELINES
from app.backtesting.metrics import compute_metrics
from app.backtesting.simulator import TradePlan, simulate
from app.config import BacktestConfig, KronosConfig, RiskConfig, StrategyConfig
from app.core.constants import Side, TradeCandidateStatus
from app.kronos.adapter import KronosAdapter
from app.logging_config import get_logger
from app.strategy import volatility_engine as ind
from app.strategy.regime_detector import detect_regime
from app.strategy.signal_scoring import score_signal

log = get_logger("backtest.walk_forward")


@dataclass
class BacktestResult:
    metrics: dict
    baseline_metrics: dict
    trades: list[dict]
    equity_curve: list[tuple]
    forecast_mode: str


def build_folds(n: int, warmup: int, test_window: int, step: int) -> list[tuple[int, int]]:
    """Return (test_start, test_end) index pairs for rolling OOS folds."""
    folds: list[tuple[int, int]] = []
    start = warmup
    while start < n:
        end = min(start + test_window, n)
        if end - start >= 2:
            folds.append((start, end))
        start += max(step, 1)
    return folds


def _make_plan_fn(
    adapter: KronosAdapter,
    *,
    symbol: str,
    timeframe: str,
    strategy: StrategyConfig,
    risk: RiskConfig,
    beta_group: str | None,
):
    def plan_fn(hist: pd.DataFrame) -> TradePlan | None:
        try:
            forecast = adapter.forecast(hist, symbol=symbol, timeframe=timeframe)
        except Exception as exc:  # not enough context etc.
            log.debug("plan_forecast_skip", symbol=symbol, error=str(exc))
            return None
        regime = detect_regime(hist, symbol=symbol, timeframe=timeframe)
        signal = score_signal(
            forecast=forecast, regime=regime, df=hist, strategy=strategy, risk=risk
        )
        if signal.status not in {
            TradeCandidateStatus.LONG_CANDIDATE,
            TradeCandidateStatus.SHORT_CANDIDATE,
        }:
            return None

        side = signal.side
        atr_val = float(ind.atr(hist).iloc[-1])
        if side == Side.LONG:
            target = forecast.last_close * (1 + forecast.q90_return)
        else:
            target = forecast.last_close * (1 + forecast.q10_return)

        return TradePlan(
            side=side,
            atr=atr_val,
            invalidation_level=signal.invalidation_level,
            forecast_target=target,
            regime=regime.regime.value,
            reason_codes=signal.reason_codes,
            beta_group=beta_group,
            uncertainty=forecast.uncertainty_score,
        )

    return plan_fn


def run_walk_forward(
    candles_by_symbol: dict[str, pd.DataFrame],
    *,
    adapter: KronosAdapter,
    backtest: BacktestConfig,
    strategy: StrategyConfig,
    risk: RiskConfig,
    kronos: KronosConfig,
    beta_groups: dict[str, str | None] | None = None,
) -> BacktestResult:
    beta_groups = beta_groups or {}
    warmup = max(backtest.warmup_candles, kronos.context_length)
    all_trades: list[dict] = []

    for symbol, df in candles_by_symbol.items():
        if len(df) < warmup + backtest.test_window_candles:
            log.warning("backtest_symbol_skipped_short_history", symbol=symbol, candles=len(df))
            continue

        plan_fn = _make_plan_fn(
            adapter, symbol=symbol, timeframe=backtest.timeframe, strategy=strategy,
            risk=risk, beta_group=beta_groups.get(symbol),
        )
        folds = build_folds(len(df), warmup, backtest.test_window_candles, backtest.step_candles)
        equity = backtest.initial_equity

        for test_start, test_end in folds:
            slice_start = max(0, test_start - warmup)
            sub = df.iloc[slice_start:test_end]
            sub_warmup = test_start - slice_start
            trades, eq = simulate(
                sub, symbol=symbol, plan_fn=plan_fn, risk=risk, warmup=sub_warmup,
                decision_frequency=backtest.decision_frequency_candles,
                max_hold_candles=backtest.max_hold_candles, fee_bps=backtest.fee_bps,
                slippage_bps=backtest.slippage_bps, slippage_model=backtest.slippage_model,
                initial_equity=equity,
            )
            if eq:
                equity = eq[-1][1]
            all_trades.extend(trades)

    # Combined realized-equity curve from sorted trade exits.
    all_trades.sort(key=lambda t: t["exit_time"])
    equity = backtest.initial_equity
    equity_curve: list[tuple] = []
    for t in all_trades:
        equity += t["net_pnl"]
        equity_curve.append((t["exit_time"], round(equity, 4)))

    metrics = compute_metrics(
        all_trades, equity_curve, initial_equity=backtest.initial_equity,
        timeframe=backtest.timeframe,
    )
    metrics["forecast_mode"] = adapter._resolved_mode.value if adapter._resolved_mode else "mock"

    baseline_metrics = _run_baselines(candles_by_symbol, backtest, warmup)
    metrics["beats_baselines"] = _beats_baselines(metrics, baseline_metrics)

    return BacktestResult(
        metrics=metrics,
        baseline_metrics=baseline_metrics,
        trades=all_trades,
        equity_curve=equity_curve,
        forecast_mode=metrics["forecast_mode"],
    )


def _run_baselines(candles_by_symbol, backtest: BacktestConfig, warmup: int) -> dict:
    out: dict[str, dict] = {}
    for name in backtest.baselines:
        fn = BASELINES.get(name)
        if fn is None:
            continue
        agg_trades: list[dict] = []
        for symbol, df in candles_by_symbol.items():
            sub = df.iloc[warmup:]
            if len(sub) < 3:
                continue
            trades, _eq = fn(
                sub, symbol, fee_bps=backtest.fee_bps, slippage_bps=backtest.slippage_bps,
                initial_equity=backtest.initial_equity,
            )
            agg_trades.extend(trades)
        agg_trades.sort(key=lambda t: t["exit_time"])
        eq = backtest.initial_equity
        curve = []
        for t in agg_trades:
            eq += t["net_pnl"]
            curve.append((t["exit_time"], eq))
        out[name] = compute_metrics(
            agg_trades, curve, initial_equity=backtest.initial_equity, timeframe=backtest.timeframe
        )
    return out


def _beats_baselines(metrics: dict, baseline_metrics: dict) -> bool:
    """True only if the strategy's Sharpe AND profit factor beat every baseline."""
    if not baseline_metrics:
        return False
    for b in baseline_metrics.values():
        if metrics["sharpe"] <= b.get("sharpe", 0) or metrics["profit_factor"] <= b.get(
            "profit_factor", 0
        ):
            return False
    return True
