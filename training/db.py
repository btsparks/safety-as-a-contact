"""Training database — separate from the main safety_as_a_contact.db."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Default: training.db in the project root
_DEFAULT_URL = "sqlite:///" + str(Path(__file__).resolve().parent.parent / "training.db")
_DB_URL = os.environ.get("TRAINING_DATABASE_URL", _DEFAULT_URL)


class TrainingBase(DeclarativeBase):
    pass


engine = create_engine(_DB_URL, connect_args={"check_same_thread": False})
TrainingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_training_db() -> None:
    """Create all training tables. Safe to call multiple times."""
    from training import models  # noqa: F401
    TrainingBase.metadata.create_all(bind=engine)


def get_training_db():
    """Yield a training DB session."""
    db = TrainingSession()
    try:
        yield db
    finally:
        db.close()
