"""Registry of Kronos model variants and a process-wide handle cache.

Loading weights is expensive, so handles are cached per (model_name, device).
"""

from __future__ import annotations

from app.config import KronosConfig
from app.kronos.loader import KronosHandles, load_real_model

# Known upstream variants (verified against shiyu-coder/Kronos README).
VARIANTS = {
    "mini": {
        "model_name": "NeoQuasar/Kronos-mini",
        "tokenizer_name": "NeoQuasar/Kronos-Tokenizer-2k",
        "max_context": 2048,
        "params": "4.1M",
    },
    "small": {
        "model_name": "NeoQuasar/Kronos-small",
        "tokenizer_name": "NeoQuasar/Kronos-Tokenizer-base",
        "max_context": 512,
        "params": "24.7M",
    },
    "base": {
        "model_name": "NeoQuasar/Kronos-base",
        "tokenizer_name": "NeoQuasar/Kronos-Tokenizer-base",
        "max_context": 512,
        "params": "102.3M",
    },
}

_cache: dict[str, KronosHandles] = {}


def get_handles(config: KronosConfig) -> KronosHandles:
    key = f"{config.model_name}@{config.device}"
    if key not in _cache:
        _cache[key] = load_real_model(config)
    return _cache[key]


def clear_cache() -> None:
    _cache.clear()


def resolve_variant(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(f"Unknown Kronos variant '{variant}'. Choose from {list(VARIANTS)}")
    return VARIANTS[variant]
