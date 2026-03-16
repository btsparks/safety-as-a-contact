"""Test photo bank — serves real jobsite photos from the training catalog.

Uses the training DB (photo_catalog + scene_analysis) to serve local photos
through the console. These are real construction photos, not stock images.
"""

import random

from training.db import TrainingSession, init_training_db
from training.models import PhotoCatalog, SceneAnalysis


def _get_analyzed_photos() -> list[dict]:
    """Load all photos that have scene analyses from the training DB."""
    init_training_db()
    db = TrainingSession()
    try:
        rows = (
            db.query(PhotoCatalog, SceneAnalysis)
            .join(SceneAnalysis, SceneAnalysis.photo_id == PhotoCatalog.id)
            .filter(PhotoCatalog.is_pdf == False)
            .order_by(PhotoCatalog.date_taken.asc())
            .all()
        )

        photos = []
        for photo, scene in rows:
            photos.append({
                "id": photo.id,
                "file_name": photo.file_name,
                "scenario": scene.scene_description or "Construction site photo",
                "hazard_hint": scene.coaching_focus or "General safety",
                "trade": scene.trade_context or "general",
                "severity": scene.severity or 3,
                "recommended_mode": scene.recommended_mode or "probe",
            })
        return photos
    finally:
        db.close()


# Cache on first load
_PHOTO_CACHE: list[dict] | None = None


def _get_cache() -> list[dict]:
    global _PHOTO_CACHE
    if _PHOTO_CACHE is None:
        _PHOTO_CACHE = _get_analyzed_photos()
    return _PHOTO_CACHE


def get_random_photo(trade: str | None = None) -> dict | None:
    """Get a random analyzed photo, optionally filtered by trade keyword."""
    pool = _get_cache()
    if not pool:
        return None

    if trade:
        trade_lower = trade.lower()
        filtered = [p for p in pool if trade_lower in (p["trade"] or "").lower()]
        if filtered:
            pool = filtered

    return random.choice(pool)


def get_photo_count() -> int:
    return len(_get_cache())
