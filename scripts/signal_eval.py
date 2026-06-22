#!/usr/bin/env python
"""Signal-validation harness: measure Kronos's RAW predictive skill, no trading.

For every forecast (no lookahead — only candles up to i are seen) we record the
model's call (p_up, median_return, quantiles) and the ACTUAL realized return over
several horizons. Output is one CSV row per (forecast, horizon), flushed
incrementally so partial results can be analyzed while it runs.

This answers the only question that matters before tuning any execution:
  - Calibration: does the actual up-rate rise with the model's p_up?
  - IC: does predicted return correlate with realized return?
  - Where: which regime / symbol / horizon carries the skill (if any).
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

os.environ.setdefault("KAT_DATABASE_URL", "sqlite:////workspace/kat/kronos.db")
os.environ.setdefault("KAT_ENABLE_SCHEDULER", "false")

from app.config import get_config_store  # noqa: E402
from app.db.session import new_session  # noqa: E402
from app.kronos.adapter import KronosAdapter  # noqa: E402
from app.repositories import candles_repo  # noqa: E402
from app.strategy.regime_detector import detect_regime  # noqa: E402

SYMBOLS = os.environ.get("SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT").split(",")
CADENCE = int(os.environ.get("CADENCE", "24"))          # forecast every N candles
HORIZONS = [int(x) for x in os.environ.get("HORIZONS", "1,4,12,24").split(",")]
OUT = os.environ.get("OUT", "/workspace/signal_eval.csv")
VERDICT_OUT = os.environ.get("VERDICT_OUT", "/workspace/spread_validation.json")
# Premise passes if Kronos's predicted spread (q90-q10) correlates with the realized
# ABSOLUTE move at this level on out-of-sample data. Below this, the volatility premise
# is unproven and BB+Kronos strategies must NOT be traded.
SPREAD_IC_PASS = float(os.environ.get("SPREAD_IC_PASS", "0.10"))


def main() -> None:
    cfg = get_config_store().kronos()
    adapter = KronosAdapter(cfg)
    db = new_session()
    ctx = cfg.context_length
    maxh = max(HORIZONS)

    out = open(OUT, "w", newline="")
    w = csv.writer(out)
    w.writerow([
        "symbol", "i", "ts", "regime", "p_up", "median_return",
        "q10_return", "q90_return", "uncertainty", "horizon",
        "realized_return", "last_close",
    ])
    out.flush()

    total = 0
    t0 = time.time()
    samples: list[tuple[int, float, float]] = []  # (horizon, predicted_spread, abs_realized)
    for sym in SYMBOLS:
        rows = candles_repo.get_candles(db, sym, "1h", ascending=True, limit=20000)
        df = candles_repo.candles_to_df(rows)
        closes = df["close"].to_numpy(float)
        n = len(df)
        print(f"[{sym}] {n} candles, forecasting every {CADENCE}h from i={ctx+5}", flush=True)
        i = ctx + 5
        while i < n - maxh:
            hist = df.iloc[: i + 1]
            try:
                fc = adapter.forecast(hist, symbol=sym, timeframe="1h")
            except Exception as exc:
                print(f"  skip i={i}: {exc}", flush=True)
                i += CADENCE
                continue
            try:
                regime = detect_regime(hist, symbol=sym, timeframe="1h").regime.value
            except Exception:
                regime = "na"
            lc = float(closes[i])
            spread = float(fc.q90_return - fc.q10_return)  # Kronos's predicted move size
            for h in HORIZONS:
                realized = (float(closes[i + h]) - lc) / lc
                w.writerow([
                    sym, i, str(df.index[i]), regime, round(fc.p_up, 4),
                    round(fc.median_return, 6), round(fc.q10_return, 6),
                    round(fc.q90_return, 6), round(fc.uncertainty_score, 4),
                    h, round(realized, 6), round(lc, 4),
                ])
                samples.append((h, spread, abs(realized)))
            out.flush()
            total += 1
            if total % 25 == 0:
                rate = (time.time() - t0) / total
                print(f"  {total} forecasts, {rate:.1f}s/ea, elapsed {(time.time()-t0)/60:.1f}m", flush=True)
            i += CADENCE
    out.close()
    db.close()
    print(f"DONE: {total} forecasts -> {OUT}", flush=True)
    _spread_validation(samples)


def _pearson(xs: list[float], ys: list[float]) -> float:
    import math
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    return cov / math.sqrt(vx * vy) if vx > 0 and vy > 0 else float("nan")


def _spread_validation(samples: list[tuple[int, float, float]]) -> None:
    """THE GATE: does Kronos's predicted spread predict the realized ABSOLUTE move?

    Writes spread_validation.json with per-horizon IC and an overall pass flag. If this
    fails, BB+Kronos strategies are NOT justified (Kronos can't even forecast move size).
    """
    print("\n=== SPREAD VALIDATION (predicted q90-q10 vs realized |move|) ===")
    per_h: dict[int, float] = {}
    best = float("-inf")
    for h in sorted(set(s[0] for s in samples)):
        xs = [s[1] for s in samples if s[0] == h]
        ys = [s[2] for s in samples if s[0] == h]
        ic = _pearson(xs, ys)
        per_h[h] = None if ic != ic else round(ic, 4)  # NaN -> None
        if ic == ic:
            best = max(best, ic)
        print(f"  h={h:>3}h  n={len(xs):5d}  spread_IC={ic:+.4f}")
    passed = best >= SPREAD_IC_PASS
    print(f"  threshold={SPREAD_IC_PASS:+.3f}  best={best:+.4f}  -> "
          f"{'PASS — volatility premise holds' if passed else 'FAIL — premise unproven, do NOT trade BB+Kronos'}")
    verdict = {"threshold": SPREAD_IC_PASS, "best_spread_ic": None if best == float('-inf') else round(best, 4),
               "passed": bool(passed), "per_horizon_ic": per_h, "n_forecasts": len(samples) // max(len(per_h), 1)}
    try:
        with open(VERDICT_OUT, "w") as f:
            json.dump(verdict, f, indent=2)
        print(f"  verdict -> {VERDICT_OUT}")
    except Exception as exc:
        print(f"  (could not write verdict: {exc})")


if __name__ == "__main__":
    main()
