"""FastAPI application entry point."""

import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.api.console import router as console_router
from backend.api.documents import router as documents_router
from backend.api.health import router as health_router
from backend.api.training import router as training_router
from backend.config import settings
from backend.database import init_db
from backend.logging_config import setup_logging
from backend.sms.handler import router as sms_router

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Safety as a Contact",
    description="SMS-delivered behavioral safety coaching for construction",
    version="0.2.0",
)

app.include_router(health_router)
app.include_router(sms_router, prefix="/api/sms")
app.include_router(console_router, prefix="/api/test")
app.include_router(training_router, prefix="/api/training")
app.include_router(documents_router)

# Templates for console UI
_template_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_template_dir)


@app.get("/console", response_class=HTMLResponse)
async def console_page(request: Request):
    """Serve the SMS test console (dev-only)."""
    if settings.is_production:
        return HTMLResponse(status_code=404, content="Not found")
    return templates.TemplateResponse("console.html", {"request": request})


@app.get("/training", response_class=HTMLResponse)
async def training_page(request: Request):
    """Serve the training review interface (dev-only)."""
    if settings.is_production:
        return HTMLResponse(status_code=404, content="Not found")
    return templates.TemplateResponse("training.html", {"request": request})


@app.get("/training/simulations", response_class=HTMLResponse)
async def simulations_page(request: Request):
    """Serve the longitudinal simulation UI (dev-only)."""
    if settings.is_production:
        return HTMLResponse(status_code=404, content="Not found")
    return templates.TemplateResponse("simulations.html", {"request": request})


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Database initialized, tables created")
