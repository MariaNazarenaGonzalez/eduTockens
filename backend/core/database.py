# TODO: Configure async SQLAlchemy engine, session maker, and database initialization utilities.

from sqlalchemy import text as sa_text
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
    """Inicializa la DB al arrancar.

    Las tablas y roles ya fueron creados por init.sql. Este método
    solo ejecuta migraciones mínimas (columnas nuevas en tablas
    existentes) de forma idempotente (IF NOT EXISTS).

    NO usa create_all — en K8s las tablas ya existen y create_all
    con un engine asincrónico puede corromper el pool de conexiones.
    """
    async with engine.begin() as conn:
        await conn.execute(
            sa_text(
                "ALTER TABLE transactions_log "
                "ADD COLUMN IF NOT EXISTS triggered_by_admin_id INTEGER REFERENCES users(id)"
            )
        )
