"""Database engine, session factory and FastAPI dependency."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# Engine is created lazily so merely importing the ORM models never requires a
# live database driver (keeps unit tests and mock-only runs dependency-light).
SessionLocal = sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False)

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            connect_args["timeout"] = 30
        _engine = create_engine(
            settings.database_url,
            echo=settings.db_echo,
            pool_pre_ping=True,
            future=True,
            connect_args=connect_args,
        )
        SessionLocal.configure(bind=_engine)
    return _engine


def new_session() -> Session:
    """Create a session, ensuring the engine exists. Caller manages lifecycle."""
    get_engine()
    return SessionLocal()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a session and always closes it."""
    db = new_session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Convenience for local/dev and tests.

    Production should use Alembic migrations (see app/db/migrations).
    """
    from app.db import models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=get_engine())
