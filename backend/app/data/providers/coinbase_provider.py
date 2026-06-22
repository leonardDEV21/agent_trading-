"""Coinbase public market data via CCXT."""

from __future__ import annotations

from app.data.providers.base_provider import CCXTProvider


class CoinbaseProvider(CCXTProvider):
    exchange_id = "coinbase"
