"""Symbol normalization and correlation-group helpers."""

from __future__ import annotations

import re


def normalize_symbol(symbol: str) -> str:
    """Canonical form: uppercase, slash-separated for pairs (e.g. ``BTC/USDT``)."""
    s = symbol.strip().upper().replace("-", "/").replace("_", "/")
    return s


def symbol_to_filename(symbol: str) -> str:
    """Filesystem-safe token for a symbol (``BTC/USDT`` -> ``BTC_USDT``)."""
    return re.sub(r"[^A-Z0-9]+", "_", normalize_symbol(symbol)).strip("_")


def base_asset(symbol: str) -> str:
    """Base leg of a pair (``BTC/USDT`` -> ``BTC``). Returns input if no slash."""
    norm = normalize_symbol(symbol)
    return norm.split("/")[0] if "/" in norm else norm


def quote_asset(symbol: str) -> str | None:
    norm = normalize_symbol(symbol)
    return norm.split("/")[1] if "/" in norm else None
