"""Shared test fixtures for backend tests."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import get_settings
from backend.db.base import Base
from backend.db.session import get_session
from backend.main import app


@pytest_asyncio.fixture
async def engine():
    settings = get_settings()
    eng = create_async_engine(settings.database_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    """
    Each test gets a session bound to a SAVEPOINT.
    Commits in handlers become savepoint releases (not real commits).
    The outer transaction rolls back at teardown so tests are isolated.
    """
    conn = await engine.connect()
    trans = await conn.begin()

    sess = AsyncSession(bind=conn, expire_on_commit=False)

    # Override commit to release and immediately re-open a nested savepoint
    # so the handler can call commit() without ending the outer tx.
    _original_commit = sess.commit

    async def _fake_commit():
        await sess.flush()

    sess.commit = _fake_commit  # type: ignore[method-assign]

    yield sess

    await sess.close()
    await trans.rollback()
    await conn.close()


@pytest_asyncio.fixture
async def client(session: AsyncSession):
    async def _override_session():
        yield session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
