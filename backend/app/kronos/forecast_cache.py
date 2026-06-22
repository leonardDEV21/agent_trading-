"""Persistent, exact-result forecast cache.

Keyed by (symbol, timeframe, context_end, model_config_hash, sample_count,
context_length, horizon) — i.e. the exact inputs that determine a forecast. On a
hit, the *same* ForecastDistribution computed earlier is returned verbatim, so any
re-run over the same candles + config (tuning a strategy, comparing setups, exit
tweaks) is instant and bit-identical. Enabled by setting the env var
KAT_FORECAST_CACHE to a sqlite path; disabled (None) otherwise — zero behavior
change when off.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime
from functools import lru_cache

from app.core.constants import ForecastMode
from app.kronos.forecast_postprocessor import ForecastDistribution

_DT_FIELDS = ("created_at", "context_start", "context_end")
_lock = threading.Lock()


class ForecastCache:
    def __init__(self, path: str):
        self.path = path
        self._con = sqlite3.connect(path, check_same_thread=False)
        self._con.execute("CREATE TABLE IF NOT EXISTS forecast_cache (k TEXT PRIMARY KEY, v TEXT)")
        self._con.commit()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(symbol, timeframe, context_end: datetime, config_hash, sample_count,
                 context_length, horizon) -> str:
        raw = (f"{symbol}|{timeframe}|{context_end.isoformat()}|{config_hash}"
               f"|{sample_count}|{context_length}|{horizon}")
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str) -> ForecastDistribution | None:
        with _lock:
            row = self._con.execute("SELECT v FROM forecast_cache WHERE k=?", (key,)).fetchone()
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        return _deserialize(json.loads(row[0]))

    def put(self, key: str, dist: ForecastDistribution) -> None:
        payload = json.dumps(_serialize(dist))
        with _lock:
            self._con.execute("INSERT OR REPLACE INTO forecast_cache (k, v) VALUES (?, ?)",
                              (key, payload))
            self._con.commit()


def _serialize(dist: ForecastDistribution) -> dict:
    d = dist.to_dict()  # mode already -> .value
    for f in _DT_FIELDS:
        d[f] = d[f].isoformat() if isinstance(d[f], datetime) else d[f]
    return d


def _deserialize(d: dict) -> ForecastDistribution:
    d = dict(d)
    for f in _DT_FIELDS:
        d[f] = datetime.fromisoformat(d[f]) if d.get(f) else None
    d["mode"] = ForecastMode(d["mode"])
    return ForecastDistribution(**d)


@lru_cache(maxsize=1)
def get_forecast_cache() -> ForecastCache | None:
    """Lazy singleton from KAT_FORECAST_CACHE env var; None if unset (caching off)."""
    path = os.environ.get("KAT_FORECAST_CACHE")
    return ForecastCache(path) if path else None
