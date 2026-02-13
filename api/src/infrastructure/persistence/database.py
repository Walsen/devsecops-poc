from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..logging import correlation_id
from .models import Base


class Database:
    """Database connection manager."""

    def __init__(self, url: str) -> None:
        self._engine = create_async_engine(url, echo=False, pool_pre_ping=True)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._attach_correlation_id_hook()

    def _attach_correlation_id_hook(self) -> None:
        """Attach SQLAlchemy event hook to inject correlation ID as SQL comment.

        This enables the "Golden Thread" — every SQL query executed by the API
        includes a /* correlation_id=<id> */ comment that appears in PostgreSQL
        logs (via pgaudit), linking DB-layer audit logs to the same request
        traced through WAF, API, and Worker layers.
        """

        @event.listens_for(self._engine.sync_engine, "before_cursor_execute", retval=True)
        def _inject_correlation_comment(conn, cursor, statement, parameters, context, executemany):
            cid = correlation_id.get("")
            if cid:
                statement = f"/* correlation_id={cid} */ {statement}"
            return statement, parameters

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
