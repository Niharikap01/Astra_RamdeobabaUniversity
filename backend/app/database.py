"""Database connectivity and session factory for NightWatch (SQLAlchemy 2.0)."""

from __future__ import annotations

import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from backend.app.config import settings

logger = logging.getLogger("nightwatch.database")

# Handle SQLite connect args
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a thread-safe database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all registered tables and ensure schema integrity."""
    from backend.app import models  # Ensure all models are loaded
    from sqlalchemy import inspect

    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        if "alerts" in existing_tables:
            columns = {col["name"] for col in inspector.get_columns("alerts")}
            if "snoozed_until" not in columns:
                logger.warning("Stale database schema detected (missing alerts.snoozed_until). Recreating database...")
                Base.metadata.drop_all(bind=engine)
    except Exception as e:
        logger.warning(f"Schema check error: {e}")

    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized.")
