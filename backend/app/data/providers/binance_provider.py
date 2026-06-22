"""Binance public market data via CCXT (default crypto provider, no API key)."""

from __future__ import annotations

from app.data.providers.base_provider import CCXTProvider


class BinanceProvider(CCXTProvider):
    exchange_id = "binance"
