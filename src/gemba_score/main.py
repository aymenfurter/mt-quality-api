"""FastAPI application factory."""
from __future__ import annotations

from fastapi import FastAPI

from .api import router as api_router
from .config import get_settings
from .db import get_database
from .ui import router as ui_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    app.include_router(ui_router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.on_event("startup")
    async def startup_event() -> None:
        await get_database(settings).create_all()

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        await get_database(settings).dispose()

    return app


app = create_app()


__all__ = ["app", "create_app"]
