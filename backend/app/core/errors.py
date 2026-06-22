"""Typed exception hierarchy.

Routes translate these into HTTP responses (see app.main exception handlers).
Using typed errors keeps failure states explicit instead of bare ValueErrors.
"""

from __future__ import annotations


class KronosTerminalError(Exception):
    """Base class for all application errors."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, detail: dict | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class ConfigError(KronosTerminalError):
    status_code = 500
    code = "config_error"


class NotFoundError(KronosTerminalError):
    status_code = 404
    code = "not_found"


class ValidationError(KronosTerminalError):
    status_code = 422
    code = "validation_error"


class DataContractError(ValidationError):
    """Raised when candle data violates the canonical data contract."""

    code = "data_contract_error"


class DataProviderError(KronosTerminalError):
    """Upstream exchange / data provider failure. Trips the kill switch."""

    status_code = 502
    code = "data_provider_error"


class ModelLoadError(KronosTerminalError):
    """The real Kronos model could not be loaded."""

    status_code = 503
    code = "model_load_error"


class MockModeForbiddenError(KronosTerminalError):
    """mock_mode=false was requested but the real model is unavailable.

    We never silently downgrade to mock when the operator demanded real output.
    """

    status_code = 503
    code = "mock_mode_forbidden"


class RiskBlockedError(KronosTerminalError):
    status_code = 409
    code = "risk_blocked"


class LiveTradingDisabledError(KronosTerminalError):
    status_code = 403
    code = "live_trading_disabled"
