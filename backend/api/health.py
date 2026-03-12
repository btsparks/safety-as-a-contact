"""Health check endpoint."""

from fastapi import APIRouter

from backend.config import settings
from backend.database import check_db_health

router = APIRouter()


@router.get("/health")
def health_check():
    db = check_db_health()
    return {
        "status": "ok" if db["status"] == "healthy" else "degraded",
        "environment": settings.environment,
        "database": db,
    }
