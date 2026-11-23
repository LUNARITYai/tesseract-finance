"""Test harness: a real Postgres, migrated once per session, one rolled-back transaction per test.

DATABASE_URL picks the test database. It defaults to ``tesseract_finance_test`` and is set
before the app reads its settings, so a developer's ``.env`` never points the suite at the
dev database.
"""

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://tf:tf@localhost:5434/tesseract_finance_test"
)

from tesseract_finance.config import get_settings
from tesseract_finance.db import get_session
from tesseract_finance.main import create_app

ROOT = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    cfg = Config(ROOT / "alembic.ini")
    cfg.attributes["configure_logger"] = False
    return cfg


def upgrade_head(connection: Connection) -> None:
    cfg = alembic_config()
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")


async def ensure_database(url: str) -> None:
    """Create the database named in ``url`` if it does not exist yet."""
    sa_url = make_url(url)
    name = sa_url.database
    assert name and ("test" in name or "migrate" in name), f"refusing to use {name!r} for tests"
    admin_dsn = sa_url.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    conn = await asyncpg.connect(admin_dsn)
    try:
        if not await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name):
            await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    url = get_settings().database_url
    await ensure_database(url)
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(upgrade_head)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session bound to an outer transaction that is rolled back after the test.

    ``create_savepoint`` turns the app's ``session.commit()`` into a savepoint release,
    so nothing a test writes escapes it.
    """
    async with engine.connect() as conn:
        outer = await conn.begin()
        session = AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await outer.rollback()


ClientFactory = Callable[..., Awaitable[AsyncClient]]


@pytest.fixture
async def make_client(session: AsyncSession) -> AsyncIterator[ClientFactory]:
    """Build an API client that shares the test session; overrides are applied per client."""
    clients: list[AsyncClient] = []

    async def make(overrides: dict | None = None) -> AsyncClient:
        app = create_app()
        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides.update(overrides or {})
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clients.append(client)
        return client

    yield make
    for client in clients:
        await client.aclose()


@pytest.fixture
async def client(make_client: ClientFactory) -> AsyncClient:
    return await make_client()
