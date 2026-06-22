"""Central configuration for the Kronos Alpha Terminal backend.

Two layers:

1. ``Settings`` — environment / secret driven (database URL, dirs, feature flags).
   Read from environment variables (and a local .env) via pydantic-settings.
   Secrets NEVER live in the JSON config files or in git.

2. ``ConfigStore`` — the versioned JSON files in ``configs/`` that drive every
   formula and threshold in the system (risk limits, strategy thresholds, the
   Kronos model choice, backtest windows, the asset universe). These are the
   knobs a trader edits *without touching source code*, per the PRD.

All config objects are typed pydantic models so the rest of the codebase gets
autocompletion and validation instead of passing raw dicts around.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
# backend/app/config.py -> parents[0]=app, [1]=backend, [2]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Environment-driven settings. Override via env vars or a .env file."""

    model_config = SettingsConfigDict(
        env_prefix="KAT_",
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- environment ---
    env: Literal["local", "ci", "prod"] = "local"
    log_level: str = "INFO"
    log_json: bool = False

    # --- database ---
    database_url: str = "postgresql+psycopg2://kronos:kronos@localhost:5432/kronos_terminal"
    db_echo: bool = False

    # --- optional services ---
    redis_url: str | None = None

    # --- directories (mounted volumes in Docker) ---
    config_dir: Path = _REPO_ROOT / "configs"
    data_dir: Path = _REPO_ROOT / "data"
    models_dir: Path = _REPO_ROOT / "models"

    # --- safety flags ---
    # Live execution is isolated behind this flag AND a separate adapter that is
    # not shipped enabled. Defaults to disabled. The paper engine ignores this.
    enable_live_trading: bool = False
    # When True the scheduler runs background jobs (ingest/forecast/signals).
    enable_scheduler: bool = True

    # --- CORS ---
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


# --------------------------------------------------------------------------- #
# Typed config models (mirror the JSON files in configs/)
# --------------------------------------------------------------------------- #
class KronosVariant(BaseModel):
    model_name: str
    tokenizer_name: str
    max_context: int
    params: str | None = None


class KronosConfig(BaseModel):
    config_version: str = "1.0.0"
    model_name: str = "NeoQuasar/Kronos-small"
    tokenizer_name: str = "NeoQuasar/Kronos-Tokenizer-base"
    model_variant: str = "small"
    context_length: int = 360
    max_context: int = 512
    forecast_horizon: int = 24
    sample_count: int = 30
    temperature: float = 1.0
    top_k: int = 0
    top_p: float = 0.9
    clip: int = 5
    # "auto" | "true" | "false" (kept as string to express the three-way choice)
    mock_mode: str = "auto"
    device: str = "auto"
    model_cache_dir: str = "/app/models/kronos_cache"
    vendor_path: str = "/app/vendor/Kronos"
    variants: dict[str, KronosVariant] = Field(default_factory=dict)

    def config_hash(self) -> str:
        """Stable hash over the fields that change forecast output.

        Used for ``model_config_hash`` on every forecast so results are
        reproducible and cache lookups never mix configs.
        """
        relevant = {
            "model_name": self.model_name,
            "tokenizer_name": self.tokenizer_name,
            "context_length": self.context_length,
            "forecast_horizon": self.forecast_horizon,
            "sample_count": self.sample_count,
            "temperature": self.temperature,
            "top_k": self.top_k,
            "top_p": self.top_p,
            "clip": self.clip,
        }
        return _hash_dict(relevant)


class KillSwitchConfig(BaseModel):
    max_consecutive_losses_per_day: int = 2
    on_data_provider_error: bool = True
    max_model_uncertainty: float = 0.85
    max_spread_bps: float = 25.0
    cooldown_minutes: int = 720


class RiskConfig(BaseModel):
    config_version: str = "1.0.0"
    account_size: float = 10000.0
    account_currency: str = "USD"
    risk_per_trade: float = 0.005
    max_daily_loss: float = 0.015
    max_open_positions: int = 2
    max_correlated_positions: int = 1
    allow_leverage: bool = False
    max_leverage: int = 1
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    min_stop_distance_pct: float = 0.003
    min_reward_risk_ratio: float = 1.0
    require_take_profit: bool = True
    kill_switch: KillSwitchConfig = Field(default_factory=KillSwitchConfig)


class EdgeWeights(BaseModel):
    volatility_penalty_scale: float = 0.5
    volatility_penalty_threshold: float = 1.25
    tiny_number: float = 1e-8


class ConfidenceBands(BaseModel):
    high: float = 0.66
    medium: float = 0.58
    low: float = 0.5


class StrategyConfig(BaseModel):
    config_version: str = "1.0.0"
    edge_formula_version: str = "v1"
    minimum_p_up: float = 0.55
    minimum_p_down: float = 0.55
    minimum_cost_adjusted_edge: float = 0.002
    minimum_asymmetry: float = 1.1
    maximum_volatility_ratio: float = 2.0
    minimum_path_quality: float = 0.4
    minimum_edge_score: float = 0.02
    require_regime_alignment: bool = True
    require_market_structure_confirmation: bool = True
    late_entry_atr_multiple: float = 1.5
    edge_weights: EdgeWeights = Field(default_factory=EdgeWeights)
    confidence_bands: ConfidenceBands = Field(default_factory=ConfidenceBands)


class BacktestConfig(BaseModel):
    config_version: str = "1.0.0"
    mode: str = "walk_forward"
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    timeframe: str = "1h"
    train_window_candles: int = 720
    test_window_candles: int = 168
    step_candles: int = 168
    forecast_horizon: int = 24
    max_hold_candles: int = 24
    decision_frequency_candles: int = 1
    warmup_candles: int = 360
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    slippage_model: str = "atr_proportional"
    initial_equity: float = 10000.0
    use_cached_forecasts: bool = True
    baselines: list[str] = Field(
        default_factory=lambda: ["buy_and_hold", "ema_trend", "atr_breakout", "random_entry"]
    )
    random_seed: int = 42


class AssetSpec(BaseModel):
    symbol: str
    exchange: str
    asset_type: str
    display_name: str | None = None
    is_market_benchmark: bool = False
    beta_group: str | None = None
    min_notional_usd: float = 10.0
    enabled: bool = True


# --------------------------------------------------------------------------- #
# Config store
# --------------------------------------------------------------------------- #
def _hash_dict(d: dict[str, Any]) -> str:
    payload = json.dumps(d, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


class ConfigStore:
    """Loads and caches the JSON config files. Re-read with :meth:`reload`."""

    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self._cache: dict[str, Any] = {}

    def _load_raw(self, filename: str) -> dict[str, Any]:
        if filename in self._cache:
            return self._cache[filename]
        path = self.config_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        self._cache[filename] = data
        return data

    def reload(self) -> None:
        self._cache.clear()

    # --- typed accessors ---
    def kronos(self) -> KronosConfig:
        return KronosConfig.model_validate(self._load_raw("kronos.default.json"))

    def risk(self) -> RiskConfig:
        return RiskConfig.model_validate(self._load_raw("risk.default.json"))

    def strategy(self) -> StrategyConfig:
        return StrategyConfig.model_validate(self._load_raw("strategy.default.json"))

    def backtest(self) -> BacktestConfig:
        return BacktestConfig.model_validate(self._load_raw("backtest.default.json"))

    def timeframes(self) -> dict[str, Any]:
        return self._load_raw("timeframes.json")

    def crypto_assets(self) -> list[AssetSpec]:
        raw = self._load_raw("assets.crypto.json")
        return [AssetSpec.model_validate(a) for a in raw.get("assets", [])]

    def stock_assets(self) -> list[AssetSpec]:
        raw = self._load_raw("assets.stocks.json")
        return [AssetSpec.model_validate(a) for a in raw.get("assets", [])]

    def all_assets(self) -> list[AssetSpec]:
        return self.crypto_assets() + self.stock_assets()

    def raw(self, filename: str) -> dict[str, Any]:
        return self._load_raw(filename)


@lru_cache
def get_config_store() -> ConfigStore:
    return ConfigStore(get_settings().config_dir)
