# TODO: Configure async SQLAlchemy engine, session maker, and database initialization utilities.

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from core.config import settings

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    pool_pre_ping=True
)

# Create async session maker
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for models
Base = declarative_base()

async def get_db() -> AsyncSession:
    """
    Dependency for getting database session
    """
    async with async_session_maker() as session:
        yield session

async def init_db():
    """
    Initialize database tables
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
