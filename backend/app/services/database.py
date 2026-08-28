"""Database engine + session management (SQLAlchemy with pgvector)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from ..core.config import get_settings
from ..core.logging import get_logger

logger = get_logger("db")

Base = declarative_base()

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.postgres_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
            pool_timeout=10,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def get_db_session():
    """FastAPI dependency yielding a DB session."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables (and pgvector extension) if not present."""
    from . import models  # noqa: F401  (register models)
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
    except Exception as exc:  # pragma: no cover - db may be down at boot
        logger.error("pgvector_extension_failed", error=str(exc))

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("db_tables_ready")
    except Exception as exc:  # pragma: no cover
        logger.error("db_create_tables_failed", error=str(exc))

