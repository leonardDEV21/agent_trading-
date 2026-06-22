#!/usr/bin/env python
"""Run forecasts (and optionally full signals) for every enabled asset.

Usage:
    python scripts/run_forecast_batch.py            # forecasts only
    python scripts/run_forecast_batch.py --signals  # forecast + regime + signal scoring
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_config_store  # noqa: E402
from app.db.session import new_session  # noqa: E402
from app.scheduler import jobs  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signals", action="store_true", help="also run regime + signal scoring")
    parser.add_argument("--timeframe", default=None)
    args = parser.parse_args()

    store = get_config_store()
    timeframe = args.timeframe or store.timeframes().get("default", "1h")
    db = new_session()
    try:
        if args.signals:
            rows = jobs.run_signals(db, timeframe=timeframe)
            db.commit()
            print(f"Ran signals for {len(rows)} assets:")
            for s in rows:
                print(f"  {s.symbol}: {s.status} edge={s.edge_score} reasons={s.reason_codes}")
        else:
            for asset in store.all_assets():
                if not asset.enabled:
                    continue
                run = jobs.forecast_symbol(db, asset.symbol, timeframe)
                db.commit()
                print(f"  {asset.symbol}: forecast_id={run.id} mode={run.mode} "
                      f"p_up={run.p_up:.3f} median_ret={run.median_return:.4f}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
