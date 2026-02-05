from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base


class Database:
    """Database connection manager."""

    def __init__(self, url: str) -> None:
        self._engine = create_async_engine(url, echo=False, pool_pre_ping=True)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def create_tables(self) -> None:
        """Create all tables (for development only)."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    def session(self) -> AsyncSession:
        """Create a new session."""
        return self._session_factory()

    async def close(self) -> None:
        """Close the database connection."""
        await self._engine.dispose()
