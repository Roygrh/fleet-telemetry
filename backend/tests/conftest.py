"""
Shared fixtures for all backend tests.

Schema is created once per test session. Before each test, all tables are
truncated (RESTART IDENTITY CASCADE) so each test starts with a clean slate.
Each test module seeds its own required data via its own autouse fixtures.

The `db` fixture is a synchronous fixture that returns an async context-manager
factory. Tests open a short-lived session with `async with db() as session:` and
the session closes before the test function returns — no session survives into
fixture teardown, which eliminates "Future attached to a different loop" errors.

Requires a running PostgreSQL with the test database already created:
    docker compose exec postgres createdb -U fleet fleet_telemetry_test
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 — registers all ORM classes with Base.metadata
from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://fleet:fleet@postgres:5432/fleet_telemetry_test",
)

_engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
_TestSession = async_sessionmaker(_engine, expire_on_commit=False)


# ------------------------------------------------------------------ #
# Dependency override — every HTTP request in tests hits the test DB  #
# ------------------------------------------------------------------ #

async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    session = _TestSession()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()


app.dependency_overrides[get_db] = _override_get_db


# ------------------------------------------------------------------ #
# Session-scoped: create schema exactly once                           #
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture(scope="session")
async def _schema() -> AsyncGenerator[None, None]:
    """Drop and recreate all tables once at the start of the test session."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


# ------------------------------------------------------------------ #
# Per-test: truncate all tables for full isolation                     #
# ------------------------------------------------------------------ #

_TRUNCATE = text(
    "TRUNCATE TABLE "
    "maintenance_records, anomalies, missions, telemetry_events, zone_counters, vehicles "
    "RESTART IDENTITY CASCADE"
)


@pytest_asyncio.fixture(autouse=True)
async def reset_db(_schema: None) -> AsyncGenerator[None, None]:
    """Truncate every table before each test; module fixtures seed what they need."""
    async with _engine.begin() as conn:
        await conn.execute(_TRUNCATE)
    yield


# ------------------------------------------------------------------ #
# Core fixtures                                                        #
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield c
    finally:
        await c.aclose()


@pytest.fixture
def db():
    """Return a factory for short-lived async sessions.

    Usage in tests:
        async with db() as session:
            result = (await session.execute(text("SELECT ..."))).scalar()

    Each `async with db()` block opens a fresh connection and closes it
    immediately on exit. Nothing survives into fixture teardown.
    """
    @asynccontextmanager
    async def _factory():
        session = _TestSession()
        try:
            yield session
        finally:
            await session.close()

    return _factory
