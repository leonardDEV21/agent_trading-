"""Canonical enums and reason codes used across the whole system.

Every strategy decision must carry a reason code (see AGENTS.md rule 9). These
enums are the single source of truth shared by the signal engine, risk engine,
backtester and the API schemas.
"""

from __future__ import annotations

from enum import Enum


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


class AssetType(str, Enum):
    CRYPTO = "crypto"
    STOCK = "stock"


class ForecastMode(str, Enum):
    REAL = "real"
    MOCK = "mock"


class Regime(str, Enum):
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE = "range"
    VOLATILITY_EXPANSION = "volatility_expansion"
    PANIC = "panic"
    UNKNOWN = "unknown"


class TradeCandidateStatus(str, Enum):
    NO_EDGE = "no_edge"
    WATCH = "watch"
    LONG_CANDIDATE = "long_candidate"
    SHORT_CANDIDATE = "short_candidate"
    BLOCKED_BY_REGIME = "blocked_by_regime"
    BLOCKED_BY_RISK = "blocked_by_risk"
    BLOCKED_BY_LATE_ENTRY = "blocked_by_late_entry"
    BLOCKED_BY_COSTS = "blocked_by_costs"
    BLOCKED_BY_UNCERTAINTY = "blocked_by_uncertainty"


class ConfidenceLabel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ReasonCode(str, Enum):
    """Machine-readable explanation attached to every signal and trade."""

    # positive
    EDGE_CONFIRMED = "edge_confirmed"
    REGIME_ALIGNED = "regime_aligned"
    STRUCTURE_CONFIRMED = "structure_confirmed"
    ASYMMETRY_FAVORABLE = "asymmetry_favorable"

    # neutral / watch
    EDGE_BELOW_THRESHOLD = "edge_below_threshold"
    PROBABILITY_BELOW_THRESHOLD = "probability_below_threshold"
    WATCH_FORMING = "watch_forming"

    # blocks
    REGIME_CONFLICT = "regime_conflict"
    NO_STRUCTURE_CONFIRMATION = "no_structure_confirmation"
    LATE_ENTRY = "late_entry"
    COST_EXCEEDS_EDGE = "cost_exceeds_edge"
    VOLATILITY_TOO_HIGH = "volatility_too_high"
    UNCERTAINTY_TOO_HIGH = "uncertainty_too_high"
    ASYMMETRY_UNFAVORABLE = "asymmetry_unfavorable"

    # risk-engine blocks
    RISK_MAX_OPEN_POSITIONS = "risk_max_open_positions"
    RISK_MAX_CORRELATED = "risk_max_correlated"
    RISK_DAILY_LOSS_LIMIT = "risk_daily_loss_limit"
    RISK_KILL_SWITCH_ACTIVE = "risk_kill_switch_active"
    RISK_NO_STOP = "risk_no_stop"
    RISK_STOP_TOO_TIGHT = "risk_stop_too_tight"
    RISK_REWARD_RISK_TOO_LOW = "risk_reward_risk_too_low"
    RISK_LEVERAGE_DISABLED = "risk_leverage_disabled"
    RISK_SIZE_BELOW_MIN_NOTIONAL = "risk_size_below_min_notional"

    # exits (paper / backtest)
    EXIT_STOP_LOSS = "exit_stop_loss"
    EXIT_TAKE_PROFIT = "exit_take_profit"
    EXIT_MAX_HOLD = "exit_max_hold"
    EXIT_REGIME_FLIP = "exit_regime_flip"
    EXIT_KILL_SWITCH = "exit_kill_switch"
    EXIT_MANUAL = "exit_manual"

    # kill-switch triggers
    KILL_CONSECUTIVE_LOSSES = "kill_consecutive_losses"
    KILL_DATA_PROVIDER_ERROR = "kill_data_provider_error"
    KILL_MODEL_UNCERTAINTY = "kill_model_uncertainty"
    KILL_SPREAD_TOO_WIDE = "kill_spread_too_wide"
    KILL_DAILY_LOSS = "kill_daily_loss"


class OrderStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class KillSwitchTrigger(str, Enum):
    CONSECUTIVE_LOSSES = "consecutive_losses"
    DATA_PROVIDER_ERROR = "data_provider_error"
    MODEL_UNCERTAINTY = "model_uncertainty"
    SPREAD_TOO_WIDE = "spread_too_wide"
    DAILY_LOSS = "daily_loss"


# Canonical OHLCV column order used everywhere a DataFrame is passed around.
CANDLE_COLUMNS = ["open", "high", "low", "close", "volume"]
# Columns the Kronos predict() API requires (note 'amount' == quote volume).
KRONOS_INPUT_COLUMNS = ["open", "high", "low", "close", "volume", "amount"]
