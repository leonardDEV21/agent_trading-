"""Trading fee model. Costs are always applied — never report gross as net."""

from __future__ import annotations


def fee_cost(notional: float, fee_bps: float) -> float:
    """Fee for one side of a trade. ``fee_bps`` is basis points (10 == 0.10%)."""
    return abs(notional) * (fee_bps / 10000.0)


def round_trip_fee(notional: float, fee_bps: float) -> float:
    return 2.0 * fee_cost(notional, fee_bps)
