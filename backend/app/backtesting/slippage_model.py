"""Slippage models. Slippage is mandatory in every simulated fill."""

from __future__ import annotations

from app.core.constants import Side


def fixed_bps_slippage_price(price: float, side: Side, slippage_bps: float) -> float:
    """Apply fixed-bps adverse slippage to a fill price.

    Buys fill higher, sells fill lower (always against the trader).
    """
    adj = price * (slippage_bps / 10000.0)
    return price + adj if side == Side.LONG else price - adj


def atr_proportional_slippage_price(
    price: float, side: Side, atr: float, factor: float = 0.05
) -> float:
    """Adverse slippage proportional to ATR (wider in volatile conditions)."""
    adj = atr * factor
    return price + adj if side == Side.LONG else price - adj


def apply_slippage(
    price: float,
    side: Side,
    *,
    model: str = "fixed_bps",
    slippage_bps: float = 5.0,
    atr: float | None = None,
) -> float:
    if model == "atr_proportional" and atr is not None:
        return atr_proportional_slippage_price(price, side, atr)
    return fixed_bps_slippage_price(price, side, slippage_bps)


def slippage_cost(fill_price: float, ideal_price: float, size: float) -> float:
    return abs(fill_price - ideal_price) * abs(size)
