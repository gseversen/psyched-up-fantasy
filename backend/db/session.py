from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import Settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings) -> AsyncEngine:
    """Create the async engine and session factory. Call once at app startup."""
    global _engine, _session_factory

    if _engine is not None:
        return _engine

    _engine = create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        echo=settings.db_echo,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return _engine


async def dispose_engine() -> None:
    """Dispose the connection pool. Call once at app shutdown."""
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine is not initialized")
    return _engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a request-scoped async session."""
    if _session_factory is None:
        raise RuntimeError("Database session factory is not initialized")

    async with _session_factory() as session:
        yield session
