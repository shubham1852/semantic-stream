"""
database/database.py
====================
SQLAlchemy async engine and session factory for SemanticStream.

Provides:
    engine       — async SQLAlchemy engine (SQLite dev / Postgres prod)
    async_session_factory — sessionmaker for async DB sessions
    get_db()     — FastAPI dependency that yields a session and closes it

Usage (in a FastAPI route):
    from backend.database.database import get_db
    from sqlalchemy.ext.asyncio import AsyncSession

    @router.get("/example")
    async def example(db: AsyncSession = Depends(get_db)):
        ...
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.config import settings
from backend.core.logging_config import get_logger

logger = get_logger(__name__)

# ── Engine ────────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,        # Log SQL in debug mode
    future=True,
    connect_args=(
        {"check_same_thread": False}
        if "sqlite" in settings.DATABASE_URL
        else {}
    ),
)

# ── Session factory ───────────────────────────────────────────────────────────

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Table initialisation ──────────────────────────────────────────────────────

async def init_db() -> None:
    """Create all tables defined in ``database.models`` if they do not exist.

    Called once at application startup from ``main.py``.
    """
    from backend.database.models import Base  # local import avoids circular deps

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("database.initialised", url=settings.DATABASE_URL)


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session and ensure it is closed after use.

    This is a FastAPI ``Depends`` dependency.  Always use it via injection
    rather than calling ``async_session_factory`` directly in route handlers.

    Yields:
        AsyncSession: A bound async SQLAlchemy session.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
