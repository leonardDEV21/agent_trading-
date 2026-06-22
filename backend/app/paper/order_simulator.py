"""Simulated fills for paper trading. No real orders are ever sent."""

from __future__ import annotations

from dataclasses import dataclass

from app.backtesting.fee_model import fee_cost
from app.backtesting.slippage_model import apply_slippage
from app.core.constants import Side


@dataclass
class Fill:
    fill_price: float
    fee: float
    slippage: float


def simulate_fill(
    *,
    side: Side,
    reference_price: float,
    size: float,
    fee_bps: float,
    slippage_bps: float,
    atr: float | None = None,
    slippage_model: str = "fixed_bps",
) -> Fill:
    fill_price = apply_slippage(
        reference_price, side, model=slippage_model, slippage_bps=slippage_bps, atr=atr
    )
    fee = fee_cost(size * fill_price, fee_bps)
    slip = abs(fill_price - reference_price) * size
    return Fill(fill_price=round(fill_price, 8), fee=round(fee, 6), slippage=round(slip, 6))
