"""Shared FastAPI dependencies."""

from backend.database import get_db

# Re-export for clean imports in route modules
__all__ = ["get_db"]
