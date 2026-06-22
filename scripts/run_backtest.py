#!/usr/bin/env python
"""Run the default walk-forward backtest and print metrics + baseline comparison."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.backtesting.walk_forward import run_walk_forward  # noqa: E402
from app.config import get_config_store  # noqa: E402
from app.db.session import new_session  # noqa: E402
from app.kronos.adapter import KronosAdapter  # noqa: E402
from app.repositories import backtests_repo, candles_repo  # noqa: E402


def main() -> None:
    store = get_config_store()
    bt, strategy, risk, kronos = store.backtest(), store.strategy(), store.risk(), store.kronos()
    beta_groups = {a.symbol: a.beta_group for a in store.all_assets()}

    db = new_session()
    try:
        candles_by_symbol = {}
        for sym in bt.symbols:
            rows = candles_repo.get_candles(db, sym, bt.timeframe, ascending=True, limit=20000)
            if len(rows) >= bt.warmup_candles + bt.test_window_candles:
                candles_by_symbol[sym] = candles_repo.candles_to_df(rows)
            else:
                print(f"  skip {sym}: only {len(rows)} candles")

        if not candles_by_symbol:
            print("No symbol has enough candles. Run `make ingest_crypto` first.")
            return

        adapter = KronosAdapter(kronos)
        result = run_walk_forward(
            candles_by_symbol, adapter=adapter, backtest=bt, strategy=strategy, risk=risk,
            kronos=kronos, beta_groups=beta_groups,
        )

        run = backtests_repo.create_run(
            db, symbols=list(candles_by_symbol.keys()), timeframe=bt.timeframe,
            config_snapshot={"backtest": bt.model_dump()},
            strategy_config_hash=strategy.edge_formula_version,
            kronos_config_hash=kronos.config_hash(), forecast_mode=result.forecast_mode,
        )
        for t in result.trades:
            backtests_repo.add_trade(db, run.id, t)
        backtests_repo.finalize_run(
            db, run, metrics=result.metrics, baseline_metrics=result.baseline_metrics
        )
        db.commit()

        print(f"\nBacktest #{run.id} (forecast mode: {result.forecast_mode})")
        print(json.dumps(result.metrics, indent=2, default=str))
        print("\nBaselines:")
        for name, m in result.baseline_metrics.items():
            print(f"  {name}: return={m['total_return']:.3%} sharpe={m['sharpe']} pf={m['profit_factor']}")
        print(f"\nBeats baselines (Sharpe & PF): {result.metrics.get('beats_baselines')}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
