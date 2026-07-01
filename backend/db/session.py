from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from backend.config import settings
from backend.observability.logging import get_logger

log = get_logger(__name__)

# The engine manages the actual connection pool to PostgreSQL
engine = create_async_engine(
    settings.database_url,
    echo=False,  # set True temporarily to see generated SQL
    pool_size=5,
    max_overflow=10,
)

# Factory that creates new AsyncSession instances on demand
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides a database session per request.

    Usage in routes:
        async def my_route(db: AsyncSession = Depends(get_db_session)):
            ...

    The session is automatically closed after the request completes,
    even if an exception occurs.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()