#!/usr/bin/env python
"""Export latest signals and the most recent backtest trades to CSV (data/exports)."""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings  # noqa: E402
from app.db.models import BacktestRun  # noqa: E402
from app.db.session import new_session  # noqa: E402
from app.repositories import signals_repo  # noqa: E402
from sqlalchemy import select  # noqa: E402


def _export(path: Path, rows: list[dict]) -> None:
    if not rows:
        print(f"  (no rows for {path.name})")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {len(rows)} rows -> {path}")


def main() -> None:
    settings = get_settings()
    out = Path(settings.data_dir) / "exports"
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    db = new_session()
    try:
        signals = signals_repo.latest_signals(db, limit=500)
        _export(
            out / f"signals_{stamp}.csv",
            [
                {
                    "symbol": s.symbol, "status": s.status, "side": s.side,
                    "edge_score": s.edge_score, "p_up": s.p_up, "cost_adjusted_edge": s.cost_adjusted_edge,
                    "asymmetry": s.asymmetry_score, "vol_ratio": s.forecast_volatility_ratio,
                    "reason_codes": "|".join(s.reason_codes or []), "as_of": s.as_of,
                }
                for s in signals
            ],
        )

        run = db.execute(select(BacktestRun).order_by(BacktestRun.id.desc()).limit(1)).scalars().first()
        if run:
            _export(
                out / f"backtest_{run.id}_trades_{stamp}.csv",
                [
                    {
                        "symbol": t.symbol, "side": t.side, "entry_time": t.entry_time,
                        "entry_price": float(t.entry_price), "exit_time": t.exit_time,
                        "exit_price": float(t.exit_price) if t.exit_price is not None else None,
                        "net_pnl": t.net_pnl, "fees": t.fees, "slippage": t.slippage,
                        "regime": t.regime, "exit_reason": t.exit_reason,
                    }
                    for t in run.trades
                ],
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
