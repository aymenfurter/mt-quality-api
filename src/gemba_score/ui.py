"""Simple HTML UI for manual scoring + monitoring."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import Settings, get_settings

router = APIRouter(include_in_schema=False)

templates_dir = Path(__file__).resolve().parents[2] / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, settings: Settings = Depends(get_settings)) -> HTMLResponse:
    context = {
        "request": request,
        "api_prefix": settings.api_v1_prefix,
        "default_threshold": 75,
        "app_name": settings.app_name,
    }
    return templates.TemplateResponse("index.html", context)


__all__ = ["router"]
