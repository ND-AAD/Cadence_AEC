"""
Shared test fixtures.

Uses an in-memory SQLite database for fast testing.
JSONB columns are compiled as JSON for SQLite compatibility.
For integration tests against PostgreSQL, use docker compose.
"""

import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.core.database import Base, get_db
from app.main import app
from app.models.core import Item, Connection, Snapshot  # noqa: F401
from app.models.infrastructure import User, Permission, Notification  # noqa: F401


# ─── SQLite compatibility: JSONB → JSON, UUID → CHAR(36) ──────

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


# Use SQLite async for tests (aiosqlite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async with test_session() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide a test HTTP client with database override."""

    async def override_get_db():
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Helper factories ─────────────────────────────────────────

@pytest_asyncio.fixture
async def make_item(db_session: AsyncSession):
    """Factory fixture for creating items."""
    async def _make(
        item_type: str = "door",
        identifier: str | None = None,
        properties: dict | None = None,
    ) -> Item:
        item = Item(
            item_type=item_type,
            identifier=identifier or f"test-{uuid.uuid4().hex[:8]}",
            properties=properties or {},
        )
        db_session.add(item)
        await db_session.flush()
        await db_session.refresh(item)
        return item
    return _make


@pytest_asyncio.fixture
async def make_connection(db_session: AsyncSession):
    """Factory fixture for creating connections."""
    async def _make(source: Item, target: Item, properties: dict | None = None) -> Connection:
        conn = Connection(
            source_item_id=source.id,
            target_item_id=target.id,
            properties=properties or {},
        )
        db_session.add(conn)
        await db_session.flush()
        await db_session.refresh(conn)
        return conn
    return _make
