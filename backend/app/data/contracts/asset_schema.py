"""Asset schema shared by the API and ingestion layers."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.core.symbols import normalize_symbol


class AssetIn(BaseModel):
    """Payload for registering an asset via the API."""

    symbol: str
    exchange: str
    asset_type: str
    display_name: str | None = None
    is_market_benchmark: bool = False
    beta_group: str | None = None
    min_notional_usd: float = 10.0
    enabled: bool = True

    @field_validator("symbol")
    @classmethod
    def _norm(cls, v: str) -> str:
        return normalize_symbol(v)


class AssetOut(AssetIn):
    id: int
