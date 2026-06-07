import os
from collections.abc import AsyncGenerator

import pytest
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings as _settings
from app.database import Base, get_db
from app.main import app

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Allow any hour so tests don't fail based on time-of-day
_settings.operating_hours_start = 0
_settings.operating_hours_end = 24

_db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/restaurant_db")
TEST_DATABASE_URL = _db_url.replace("/restaurant_db", "/restaurant_test")

_TRUNCATE_TABLES = ["bookings", "refresh_tokens", "users", "restaurant_tables"]

_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def setup_schema():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


@pytest.fixture()
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session
        await session.rollback()
        truncate_sql = ", ".join(f'"{t}"' for t in _TRUNCATE_TABLES)
        await session.execute(text(f"TRUNCATE TABLE {truncate_sql} RESTART IDENTITY CASCADE"))
        await session.commit()


@pytest.fixture()
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
