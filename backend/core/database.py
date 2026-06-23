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

    Las tablas y roles ya fueron creados por init.sql (Dev: docker-entrypoint-initdb.d,
    Prod: ConfigMap en K8s). Este método solo hace safety checks:

    1. `create_all(checkfirst=True)` — crea SOLO las tablas que no existen.
    2. `ALTER TABLE IF NOT EXISTS` — agrega columnas nuevas a tablas ya existentes
       sin romper si la columna ya está.
    """
    async with engine.begin() as conn:
        # 1. Crear tablas faltantes sin tocar las que ya están
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)

        # 2. Agregar columnas nuevas que init.sql todavía no tiene
        #    (migración mínima — sin Alembic)
        await conn.execute(
            sa_text(
                "ALTER TABLE transactions_log "
                "ADD COLUMN IF NOT EXISTS triggered_by_admin_id INTEGER REFERENCES users(id)"
            )
        )
