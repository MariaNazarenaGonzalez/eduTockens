# Cómo correr los tests localmente

## Requisitos previos

- Python 3.10+
- No se necesita Docker ni Postgres corriendo — los tests usan SQLite en memoria.

---

## 1. Crear el entorno virtual

Desde la carpeta **`backend/`**:

```bash
python -m venv .venv
source .venv/bin/activate       # Linux / macOS
# .venv\Scripts\activate        # Windows
```

## 2. Instalar dependencias

```bash
# Dependencias de producción (necesarias para importar el código)
pip install -r requirements.txt

# Dependencias exclusivas de testing
pip install -r requirements-dev.txt
```

## 3. Configurar variables de entorno mínimas

Los tests no necesitan DB real ni NCT, pero `core/config.py` carga `.env`
al importarse. Si no existe `.env`, usa los valores por defecto (que son
válidos para testing).

Si querés asegurarte de que no lea un `.env` de producción, podés forzar
las variables mínimas:

```bash
export DATABASE_URL="sqlite+aiosqlite:///:memory:"
export JWT_SECRET="test-secret-key"
```

O simplemente dejá que tome los defaults de `config.py` (también funciona).

## 4. Correr los tests

```bash
# Desde backend/
pytest
```

### Opciones útiles

```bash
# Con reporte de cobertura
pytest --cov=. --cov-report=term-missing

# Solo un archivo
pytest tests/test_crypto.py -v

# Solo los tests puro Python (sin DB, más rápidos)
pytest tests/test_crypto.py tests/test_security.py tests/test_schemas.py -v

# Con salida detallada
pytest -v

# Detener al primer fallo
pytest -x

# Mostrar los 5 tests más lentos
pytest --durations=5
```

## 5. Estructura de los tests

```
backend/
├── pytest.ini                  # Configuración: asyncio_mode=auto, testpaths=tests
├── requirements-dev.txt        # pytest, pytest-asyncio, aiosqlite, etc.
└── tests/
    ├── conftest.py             # Fixtures: DB en memoria, client HTTP, usuarios
    ├── test_crypto.py          # core/crypto.py (puro Python)
    ├── test_security.py        # core/security.py (puro Python)
    ├── test_schemas.py         # schemas/schemas.py (Pydantic)
    ├── test_auth_router.py     # POST /register, /login, /logout
    ├── test_products_router.py # GET /products, /products/{id}
    ├── test_purchases_router.py# POST /purchases, GET /purchases/me
    ├── test_students_router.py # GET /students/{legajo}/balance y /transactions
    ├── test_admin_router.py    # /admin/vendors, /products, /earn, /stats
    └── test_relay_router.py    # POST /transactions/relay
```

## 6. Notas técnicas

- **Sin Postgres real**: se usa `aiosqlite` (SQLite async en memoria).
  Los `CheckConstraint` con sintaxis de Postgres (`~` para regex) se eliminan
  automáticamente del metadata antes de crear las tablas de test.
- **Sin NCT real**: los endpoints que llaman al NCT tienen el cliente
  mockeado con `unittest.mock.AsyncMock`.
- **Sin servidor levantado**: `httpx.AsyncClient` con `ASGITransport`
  llama directamente a la app ASGI sin puerto TCP.
- **Aislamiento**: cada test recibe su propia base de datos SQLite en memoria.
  No hay estado compartido entre tests.
