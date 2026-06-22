"""Safe loading of the real Kronos model.

Kronos is NOT a PyPI package. The upstream repo (shiyu-coder/Kronos) is cloned
into ``vendor_path`` and exposes a ``model`` package with Kronos / KronosTokenizer
/ KronosPredictor. We add that path to sys.path lazily and convert every failure
mode (missing torch, missing vendor dir, no model files, no GPU) into a clean
ModelLoadError so the caller can fall back to clearly-labeled mock mode.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from app.config import KronosConfig
from app.core.errors import ModelLoadError
from app.logging_config import get_logger

log = get_logger("kronos.loader")


@dataclass
class KronosHandles:
    model: object
    tokenizer: object
    predictor: object
    device: str
    model_name: str
    max_context: int


def _resolve_device(requested: str) -> str:
    if requested and requested != "auto":
        return requested
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda:0"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:  # torch not installed -> CPU
        pass
    return "cpu"


def real_model_available(config: KronosConfig) -> tuple[bool, str]:
    """Cheap check (no model download) of whether real mode *could* work.

    Returns (available, reason). reason explains the blocker when not available.
    """
    try:
        import torch  # noqa: F401
    except ImportError:
        return False, "torch not installed (install requirements-kronos.txt)"

    vendor = Path(config.vendor_path)
    if not vendor.is_absolute():
        repo_root = Path(__file__).resolve().parents[3]
        vendor = (repo_root / vendor).resolve()

    if not (vendor / "model").exists() and not _model_importable():
        return False, f"Kronos source not found at {vendor} (clone shiyu-coder/Kronos)"
    return True, "ok"


def _model_importable() -> bool:
    try:
        import importlib

        importlib.import_module("model")
        return True
    except Exception:
        return False


def load_real_model(config: KronosConfig) -> KronosHandles:
    """Load the real Kronos model + tokenizer. Raise ModelLoadError on any failure."""
    vendor = Path(config.vendor_path)
    if not vendor.is_absolute():
        repo_root = Path(__file__).resolve().parents[3]
        vendor = (repo_root / vendor).resolve()

    if vendor.exists() and str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))

    try:
        from model import Kronos, KronosPredictor, KronosTokenizer  # type: ignore
    except Exception as exc:
        raise ModelLoadError(
            f"Could not import Kronos from '{vendor}'. Clone shiyu-coder/Kronos and "
            f"pip install -r requirements-kronos.txt. ({exc})"
        ) from exc

    device = _resolve_device(config.device)
    try:
        tokenizer = KronosTokenizer.from_pretrained(config.tokenizer_name)
        model = Kronos.from_pretrained(config.model_name)
        predictor = KronosPredictor(
            model, tokenizer, device=device, max_context=config.max_context, clip=config.clip
        )
    except Exception as exc:
        raise ModelLoadError(
            f"Failed to load Kronos weights ({config.model_name} / {config.tokenizer_name}). "
            f"Check network access to Hugging Face and the model cache. ({exc})"
        ) from exc

    log.info("kronos_loaded", model=config.model_name, device=device)
    return KronosHandles(
        model=model,
        tokenizer=tokenizer,
        predictor=predictor,
        device=device,
        model_name=config.model_name,
        max_context=config.max_context,
    )
