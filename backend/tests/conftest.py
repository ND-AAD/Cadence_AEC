"""
Shared test fixtures.

Uses an in-memory SQLite database for fast testing.
JSONB columns are compiled as JSON for SQLite compatibility.
For integration tests against PostgreSQL, use docker compose.
"""

import uuid
from typing import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.api.deps import get_current_user
from app.core.database import Base, get_db
from app.main import app
from app.models.core import Item, Connection, Snapshot  # noqa: F401
from app.models.infrastructure import User, Permission, Notification  # noqa: F401
from app.services.dynamic_types import resolve_user_firm, seed_firm_types


# ─── Test user for auth override ─────────────────────────────

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_USER_EMAIL = "test@test.com"
TEST_USER_NAME = "Test User"


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
        # Enable foreign key enforcement in SQLite (required for CASCADE).
        await conn.execute(text("PRAGMA foreign_keys = ON"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session with firm vocabulary pre-seeded.

    After DYN-0, spatial types (door, room, etc.) live in firm vocabulary,
    not the OS ITEM_TYPES registry. We seed them here so any test that creates
    spatial items or looks up their type config will work.
    """
    async with test_session() as session:
        # Create a minimal user + firm + starter types for every test
        user = User(
            id=TEST_USER_ID,
            email=TEST_USER_EMAIL,
            name=TEST_USER_NAME,
            password_hash="not-a-real-hash",
        )
        session.add(user)
        await session.flush()

        firm = await resolve_user_firm(session, TEST_USER_ID)
        await seed_firm_types(session, firm.id)

        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide a test HTTP client with database and auth overrides."""

    # User and firm types already seeded by db_session fixture

    async def override_get_db():
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    async def override_get_current_user() -> User:
        """Bypass JWT validation in tests — return the test user."""
        result = await db_session.execute(select(User).where(User.id == TEST_USER_ID))
        return result.scalar_one()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Helper factories ─────────────────────────────────────────


@pytest_asyncio.fixture
async def make_item(db_session: AsyncSession):
    """Factory fixture for creating items. Auto-creates permission for project items."""

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

        # Auto-create permission for project items so API access checks pass.
        # Only if the test user exists (i.e., `client` fixture was used).
        if item_type == "project":
            user_exists = await db_session.execute(
                select(User).where(User.id == TEST_USER_ID)
            )
            if user_exists.scalar_one_or_none():
                perm = Permission(
                    user_id=TEST_USER_ID,
                    scope_item_id=item.id,
                    role="admin",
                    can_resolve_conflicts=True,
                    can_import=True,
                    can_edit=True,
                )
                db_session.add(perm)
                await db_session.flush()

        return item

    return _make


@pytest_asyncio.fixture
async def make_connection(db_session: AsyncSession):
    """Factory fixture for creating connections."""

    async def _make(
        source: Item, target: Item, properties: dict | None = None
    ) -> Connection:
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
