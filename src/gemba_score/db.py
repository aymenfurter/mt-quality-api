"""Database utilities and SQLAlchemy helpers."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import Settings, get_settings
from .models import Base


class Database:
    """Encapsulates Async SQLAlchemy engine + session factory."""

    def __init__(self, url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(url, future=True, echo=False)
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    def sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        return self._sessionmaker

    async def create_all(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self._engine.dispose()


_database: Database | None = None


def get_database(settings: Settings | None = None) -> Database:
    """Singleton-style access to the configured database."""

    global _database
    settings = settings or get_settings()
    if _database is None:
        _database = Database(settings.database_url)
    return _database


def reset_database() -> None:
    """Helper for tests to drop the cached database instance."""

    global _database
    _database = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an AsyncSession."""

    database = get_database()
    async_session = database.sessionmaker()
    async with async_session() as session:
        yield session
