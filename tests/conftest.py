# autopep8: off
import os
os.environ.setdefault('DB_HOST', 'localhost')
os.environ.setdefault('DB_PORT', '5432')
os.environ.setdefault('DB_USER', 'test')
os.environ.setdefault('DB_PASS', 'test')
os.environ.setdefault('DB_NAME', 'test')

import pytest
from typing import AsyncGenerator
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.core.database.base import Base
from app.main import app
# autopep8: on

# Тестовая база данных (SQLite в памяти для быстрых тестов)
TEST_DATABASE_URL = 'sqlite+aiosqlite:///:memory:'


@pytest.fixture(scope='session')
async def test_engine():
    """Создание тестового движка БД."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Создание тестовой сессии БД с откатом после каждого теста."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP клиент для тестирования FastAPI endpoints."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url='http://test',
    ) as client:
        yield client
