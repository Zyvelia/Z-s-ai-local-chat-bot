from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True, pool_size=settings.database_pool_size, max_overflow=settings.database_max_overflow, pool_timeout=settings.database_pool_timeout, pool_recycle=1800)
Session = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncIterator[AsyncSession]:
    async with Session() as session:
        yield session
