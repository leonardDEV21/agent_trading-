"""FastAPI application entrypoint.

Wires routers, CORS, structured exception handling, and (optionally) the
scheduler. Live trading is never enabled here — it is gated by config and a
separate, unshipped adapter.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    routes_assets,
    routes_backtests,
    routes_candles,
    routes_forecasts,
    routes_health,
    routes_paper_trading,
    routes_risk,
    routes_settings,
    routes_signals,
)
from app.config import get_settings
from app.core.errors import KronosTerminalError
from app.db.session import init_db
from app.logging_config import configure_logging, get_logger
from app.scheduler.runner import shutdown_scheduler, start_scheduler

configure_logging()
log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    try:
        init_db()
        log.info("db_initialized")
    except Exception as exc:  # DB may be unavailable at import time in some envs
        log.error("db_init_failed", error=str(exc))
    start_scheduler()
    log.info(
        "app_started", env=settings.env, live_trading=settings.enable_live_trading,
        scheduler=settings.enable_scheduler,
    )
    yield
    shutdown_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Kronos Alpha Terminal",
        version="0.1.0",
        description="Local-first AI-assisted trading research terminal (paper/research only).",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(KronosTerminalError)
    async def _handle_app_error(request: Request, exc: KronosTerminalError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "detail": exc.detail},
        )

    for module in (
        routes_health,
        routes_assets,
        routes_candles,
        routes_forecasts,
        routes_signals,
        routes_backtests,
        routes_paper_trading,
        routes_risk,
        routes_settings,
    ):
        app.include_router(module.router)

    @app.get("/", tags=["meta"])
    def root():
        return {
            "name": "Kronos Alpha Terminal",
            "mode": "paper/research",
            "live_trading_enabled": settings.enable_live_trading,
            "docs": "/docs",
        }

    return app


app = create_app()
