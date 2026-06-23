# DEO GLORIA

"""Fixtures compartidas para todos los tests del backend eduTockens.

Estrategia de base de datos:
- Se usa SQLite en memoria (aiosqlite) en lugar de PostgreSQL real.
- Los CheckConstraint con sintaxis exclusiva de Postgres (operador regex ~)
  se eliminan del metadata de SQLAlchemy ANTES de create_all para evitar
  errores en SQLite. Esto sucede una sola vez al importar este conftest.
- Cada test recibe una DB fresca (engine propio en :memory:) para garantizar
  aislamiento total sin necesidad de rollbacks explícitos.

Estrategia de lifespan:
- main.init_db() ejecuta un ALTER TABLE específico de Postgres. Se parchea
  con AsyncMock para que el lifespan no falle en SQLite.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Agrega backend/ al sys.path para que los imports funcionen
# independientemente de desde dónde se invoque pytest.
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import CheckConstraint  # noqa: E402  (import después del sys.path)

# ---------------------------------------------------------------------------
# Eliminar CheckConstraints de Postgres del metadata global (una sola vez)
# ---------------------------------------------------------------------------
from core.database import Base  # noqa: E402

for _tbl in Base.metadata.tables.values():
    _pg_constraints = {c for c in _tbl.constraints if isinstance(c, CheckConstraint)}
    for _c in _pg_constraints:
        _tbl.constraints.discard(_c)

# ---------------------------------------------------------------------------
# Imports del resto del proyecto (después de parchear metadata)
# ---------------------------------------------------------------------------
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402

from main import app  # noqa: E402
from core.database import get_db  # noqa: E402
from core.security import create_access_token, hash_password  # noqa: E402
from core.crypto import generate_keypair_hex  # noqa: E402
from models.models import Product, Role, TransactionLog, User, Vendor  # noqa: E402

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixture: sesión de base de datos (una DB fresca por test)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_session():
    """Base de datos SQLite en memoria. Crea tablas y roles semilla."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("INSERT INTO roles (id, name) VALUES (1, 'student')"))
        await conn.execute(text("INSERT INTO roles (id, name) VALUES (2, 'admin')"))

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Fixture: cliente HTTP de la app FastAPI
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(db_session):
    """AsyncClient conectado a la app FastAPI con la DB de test inyectada."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    # init_db() usa sintaxis ALTER TABLE exclusiva de Postgres → se parchea.
    with patch("main.init_db", new_callable=AsyncMock):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fixtures: usuarios de prueba
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def student_user(db_session) -> User:
    """Usuario con rol 'student' persistido en la DB de test."""
    _, pub_key = generate_keypair_hex()
    user = User(
        legajo="S12345",
        name="Estudiante Test",
        email="student@test.com",
        public_key=pub_key,
        password_hash=hash_password("password123"),
        role_id=1,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session) -> User:
    """Usuario con rol 'admin' persistido en la DB de test."""
    _, pub_key = generate_keypair_hex()
    user = User(
        legajo="A99999",
        name="Admin Test",
        email="admin@test.com",
        public_key=pub_key,
        password_hash=hash_password("adminpass123"),
        role_id=2,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Helpers: headers de autenticación
# ---------------------------------------------------------------------------

def auth_headers(user: User, role: str) -> dict:
    """Genera headers Authorization con JWT válido para el usuario dado."""
    token = create_access_token(
        user_id=user.id,
        legajo=user.legajo,
        role=role,
        public_key=user.public_key,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def student_headers(student_user: User) -> dict:
    return auth_headers(student_user, "student")


@pytest.fixture
def admin_headers(admin_user: User) -> dict:
    return auth_headers(admin_user, "admin")


# ---------------------------------------------------------------------------
# Fixtures: datos de prueba (vendor, product)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def sample_vendor(db_session) -> Vendor:
    """Vendor de prueba persistido."""
    _, pub_key = generate_keypair_hex()
    vendor = Vendor(name="Fotocopiadora Test", public_key=pub_key)
    db_session.add(vendor)
    await db_session.commit()
    await db_session.refresh(vendor)
    return vendor


@pytest_asyncio.fixture
async def sample_product(db_session, sample_vendor) -> Product:
    """Producto activo con stock persistido."""
    product = Product(
        name="Café",
        description="Café largo",
        price_points=50,
        stock=10,
        active=True,
        vendor_id=sample_vendor.id,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product
