"""Real-mode prediction service: ties model handles + sampler together.

Kept separate from the adapter so the real-model plumbing can be swapped or
mocked in tests without touching the adapter's mock/real decision logic.
"""

from __future__ import annotations

import numpy as np

import threading

from app.config import KronosConfig
from app.kronos.feature_builder import ModelContext
from app.kronos.loader import real_model_available
from app.kronos.model_registry import get_handles
from app.kronos.sampler import generate_real_paths


# Process-wide lock to serialize model inference requests, preventing race
# conditions on the stateful positional embedding caches in the shared model.
_predict_lock = threading.Lock()


class RealForecaster:
    """Loads (cached) handles and produces real sample paths."""

    def __init__(self, config: KronosConfig):
        self.config = config

    def available(self) -> tuple[bool, str]:
        return real_model_available(self.config)

    def sample_paths(self, ctx: ModelContext) -> np.ndarray:
        handles = get_handles(self.config)
        with _predict_lock:
            return generate_real_paths(handles, ctx, self.config)
