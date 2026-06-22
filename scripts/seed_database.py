#!/usr/bin/env python
"""Create tables, register the configured asset universe, optionally ingest candles.

Usage:
    python scripts/seed_database.py             # create tables + register assets
    python scripts/seed_database.py --ingest    # also ingest default candles
    python scripts/seed_database.py --reset-paper
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_config_store  # noqa: E402
from app.db.models import Asset  # noqa: E402
from app.db.session import init_db, new_session  # noqa: E402
from app.repositories import paper_trades_repo  # noqa: E402
from app.scheduler import jobs  # noqa: E402
from sqlalchemy import select  # noqa: E402


def register_assets(db) -> int:
    store = get_config_store()
    n = 0
    for a in store.all_assets():
        exists = db.execute(
            select(Asset).where(Asset.symbol == a.symbol, Asset.exchange == a.exchange)
        ).scalars().first()
        if exists:
            continue
        db.add(Asset(**a.model_dump()))
        n += 1
    db.commit()
    return n


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ingest", action="store_true", help="ingest default candles after seeding")
    parser.add_argument("--reset-paper", action="store_true", help="wipe paper orders")
    args = parser.parse_args()

    print("Creating tables…")
    init_db()
    db = new_session()
    try:
        if args.reset_paper:
            deleted = paper_trades_repo.reset_paper(db)
            db.commit()
            print(f"Reset paper book: deleted {deleted} orders")
            return

        added = register_assets(db)
        print(f"Registered {added} new assets")

        if args.ingest:
            print("Ingesting candles (Binance public via CCXT)…")
            results = jobs.run_ingest(db, lookback_candles=1500)
            db.commit()
            for sym, r in results.items():
                print(f"  {sym}: inserted {r['inserted']}, gaps {r['gaps']}")
    finally:
        db.close()
    print("Done.")


if __name__ == "__main__":
    main()
