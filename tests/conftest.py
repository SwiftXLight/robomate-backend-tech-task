"""Pytest configuration and fixtures."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db.database import get_session_factory, get_engine
from app.services.redis_service import get_redis_client
from app.models.event import EventCreate


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get test database session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        # Start transaction
        await session.begin()
        yield session
        # Rollback transaction
        await session.rollback()


@pytest_asyncio.fixture
async def redis_client():
    """Get Redis client for tests."""
    client = await get_redis_client()
    # Clear test keys
    await client.flushdb()
    yield client
    # Cleanup
    await client.flushdb()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Get async HTTP client for API tests."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_event() -> EventCreate:
    """Create a sample event for testing."""
    return EventCreate(
        event_id=uuid4(),
        user_id="user_123",
        event_type="page_view",
        occurred_at=datetime.now(),
        properties={"page": "/home", "duration": 5.2},
    )


@pytest.fixture
def sample_events(sample_event: EventCreate) -> list[EventCreate]:
    """Create multiple sample events."""
    return [
        sample_event,
        EventCreate(
            event_id=uuid4(),
            user_id="user_456",
            event_type="purchase",
            occurred_at=datetime.now(),
            properties={"amount": 99.99, "currency": "USD"},
        ),
        EventCreate(
            event_id=uuid4(),
            user_id="user_123",
            event_type="click",
            occurred_at=datetime.now(),
            properties={"button": "cta"},
        ),
    ]


@pytest_asyncio.fixture
async def clean_db() -> AsyncGenerator[None, None]:
    """Clean database before and after tests."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE events CASCADE"))
    yield
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE events CASCADE"))

