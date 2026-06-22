"""Settings endpoints: view all configs and update them WITHOUT editing source.

PUT validates the payload against the typed config model before writing the JSON
file, then reloads the in-memory store. This is how a trader changes risk limits,
strategy thresholds, the Kronos model, fees, slippage, etc. from the UI.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import (
    BacktestConfig,
    KronosConfig,
    RiskConfig,
    StrategyConfig,
    get_config_store,
    get_settings,
)
from app.core.errors import ValidationError
from app.db.models import Config
from app.db.session import get_db

router = APIRouter(tags=["settings"])

# config name -> (filename, validating model | None)
_EDITABLE = {
    "risk": ("risk.default.json", RiskConfig),
    "strategy": ("strategy.default.json", StrategyConfig),
    "kronos": ("kronos.default.json", KronosConfig),
    "backtest": ("backtest.default.json", BacktestConfig),
    "timeframes": ("timeframes.json", None),
    "assets.crypto": ("assets.crypto.json", None),
    "assets.stocks": ("assets.stocks.json", None),
}


@router.get("/settings")
def get_all_settings() -> dict:
    store = get_config_store()
    s = get_settings()
    return {
        "env": s.env,
        "live_trading_enabled": s.enable_live_trading,
        "scheduler_enabled": s.enable_scheduler,
        "configs": {
            "risk": store.risk().model_dump(),
            "strategy": store.strategy().model_dump(),
            "kronos": store.kronos().model_dump(),
            "backtest": store.backtest().model_dump(),
            "timeframes": store.timeframes(),
            "assets_crypto": [a.model_dump() for a in store.crypto_assets()],
            "assets_stocks": [a.model_dump() for a in store.stock_assets()],
        },
        "editable": list(_EDITABLE.keys()),
    }


class SettingsUpdate(BaseModel):
    name: str
    payload: dict


@router.put("/settings")
def update_settings(req: SettingsUpdate, db: Session = Depends(get_db)) -> dict:
    if req.name not in _EDITABLE:
        raise ValidationError(
            f"Unknown config '{req.name}'", detail={"editable": list(_EDITABLE.keys())}
        )
    filename, model = _EDITABLE[req.name]

    if model is not None:
        try:
            validated = model.model_validate(req.payload)
            payload = validated.model_dump()
        except Exception as exc:
            raise ValidationError(f"Invalid {req.name} config: {exc}") from exc
    else:
        payload = req.payload

    store = get_config_store()
    path = store.config_dir / filename
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    store.reload()

    # keep an audit snapshot of every config change
    db.add(Config(name=req.name, config_hash=_hash(payload), payload=payload))

    return {"updated": req.name, "file": str(path)}


def _hash(payload: dict) -> str:
    import hashlib

    raw = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]
