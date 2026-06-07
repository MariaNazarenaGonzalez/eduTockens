# eduTockens

Sistema de Aplicación Web — Puntos Académicos sobre Blockchain

Este repositorio contiene la capa de aplicación (Frontend, Backend, Base de Datos) para el TP Integrador — Blockchain Distribuida y CUDA.

## Componentes

- **Frontend:** HTML5, CSS3, JavaScript vanilla
- **Backend:** Python 3.11 con FastAPI
- **Base de Datos:** PostgreSQL 15

## Estructura del Frontend

### Archivos Principales

#### CSS
- **`frontend/css/styles.css`** - Estilos base con variables CSS, componentes de UI (botones, tarjetas, formularios), animaciones y layouts responsivos.

#### Páginas Públicas
- **`frontend/index.html`** - Homepage pública con descripción del sistema y enlaces a login/registro. Accesible sin autenticación.

#### Autenticación
- **`frontend/pages/login.html`** - Formulario de login con tabs para Estudiante/Administrador. Almacena JWT en localStorage.
- **`frontend/pages/register.html`** - Formulario de registro para nuevos estudiantes con validación de campos.

#### Dashboard de Estudiante
- **`frontend/pages/home.html`** - Homepage del estudiante con balance en blockchain, métricas (ganados/gastados/transacciones) e historial reciente.
- **`frontend/pages/marketplace.html`** - Grilla de productos disponibles con precios en puntos. Filtro de categorías y navegación a compra.
- **`frontend/pages/purchase.html`** - Confirmación de compra con detalle del producto, cálculo de saldo restante y validación.
- **`frontend/pages/profile.html`** - Perfil del estudiante con datos, identificador en blockchain, estadísticas y acceso a cambiar contraseña.

#### Panel de Administración
- **`frontend/pages/admin.html`** - Dashboard admin con estadísticas globales, tabs para emisión de puntos y gestión de productos.

### Scripts JavaScript

#### Autenticación
- **`frontend/js/auth.js`** - Funciones para login, register, logout, gestión de tokens JWT y validación de autenticación.

#### Lógica de Páginas
- **`frontend/js/home.js`** - Carga de balance desde NCT, historial de transacciones, actualización de métricas del dashboard.
- **`frontend/js/marketplace.js`** - Carga de productos disponibles, renderizado de grid, navegación a compra.
- **`frontend/js/purchase.js`** - Confirmación de compra, validación de saldo, emisión de transacción SPEND al NCT.
- **`frontend/js/admin.js`** - Emisión de puntos (EARN), gestión de productos, carga de estadísticas del sistema.

## Estructura del Backend

### Configuración (`backend/core/`)
- **`config.py`** - Configuración de aplicación desde variables de entorno (DATABASE_URL, JWT_SECRET, NCT_BASE_URL, etc.)
- **`database.py`** - Configuración de SQLAlchemy async engine, session maker, Base ORM, función init_db()
- **`security.py`** - Funciones de autenticación: hash_password(), verify_password(), create_access_token(), verify_token(), get_current_user()

### Modelos ORM (`backend/models/`)
- **`models.py`** - Modelos SQLAlchemy para: Role, User (legajo, name, email, password_hash), Product (name, price_points, stock, image_data), Purchase (user_id, product_id, points_spent, nct_transaction_id)

### Esquemas Pydantic (`backend/schemas/`)
- **`schemas.py`** - Esquemas de validación para requests/responses: UserRegister, UserLogin, TokenResponse, ProductCreate/Update, PurchaseCreate, EarnRequest, AdminStats

### Routers API (`backend/routers/`)
- **`auth.py`** - Endpoints: POST /auth/register, POST /auth/login, POST /auth/logout
- **`users.py`** - Endpoint: GET /users/me (obtener perfil del usuario autenticado)
- **`products.py`** - Endpoints: GET /products, GET /products/{id}, GET /products/{id}/image
- **`purchases.py`** - Endpoints: POST /purchases, GET /purchases/me (historial del usuario)
- **`admin.py`** - Endpoints: POST /admin/earn (emitir puntos), GET /admin/stats, GET/POST /admin/products, DELETE /admin/products/{id}

### Servicios (`backend/services/`)
- **`nct_client.py`** - Cliente HTTP para NCT: get_balance(), get_transactions(), emit_earn(), emit_spend()

### Base de Datos (`db/`)
- **`init.sql`** - Script de inicialización con tablas: roles, users, products, purchases e índices

## Flujo de Uso

### Estudiante
1. **Registro** (`pages/register.html`) - Crear cuenta con legajo, nombre, email y contraseña
2. **Login** (`pages/login.html`) - Autenticarse y recibir JWT
3. **Dashboard** (`pages/home.html`) - Ver saldo confirmado, historial y acciones rápidas
4. **Marketplace** (`pages/marketplace.html`) - Explorar productos disponibles
5. **Compra** (`pages/purchase.html`) - Confirmar compra y emitir transacción SPEND
6. **Perfil** (`pages/profile.html`) - Ver datos, identificador en blockchain y estadísticas

### Administrador
1. **Login** (`pages/login.html`) - Autenticarse como admin
2. **Dashboard** (`pages/admin.html`) - Ver estadísticas globales
3. **Emisión de Puntos** - Emitir EARN a estudiantes por actividades académicas
4. **Gestión de Productos** - Crear, editar, eliminar productos del marketplace

## Integración Backend

El frontend se comunica con el backend a través de una API REST en `http://localhost:8000/api`. Endpoints principales:

**Autenticación:**
- `POST /auth/register` - Registrar estudiante
- `POST /auth/login` - Login y obtener JWT

**Estudiante:**
- `GET /students/{legajo}/balance` - Consultar saldo
- `GET /students/{legajo}/transactions` - Historial de transacciones
- `POST /purchases` - Emitir transacción SPEND

**Administrador:**
- `POST /admin/earn` - Emitir puntos (EARN)
- `GET /admin/products` - Listar productos
- `POST /admin/products` - Crear producto

## Stack Tecnológico

### Frontend
- **HTML5** - Estructura semántica
- **CSS3** - Estilos responsivos con custom properties
- **JavaScript Vanilla** - Sin frameworks, máxima compatibilidad
- **Fuentes:** DM Sans (body), DM Mono (code)
- **Iconos:** Emojis Unicode + SVG inline

### Autenticación
- **JWT (JSON Web Tokens)** - Token-based stateless auth
- **localStorage** - Almacenamiento de tokens y user data
- **Headers Bearer** - Inclusión de token en requests

## Despliegue Local

```bash
# Levantar contenedores
docker compose up --build

# Acceder al frontend
http://localhost

# Documentación API (backend)
http://localhost:8000/docs
```

## Variables de Entorno (Backend)

Copiar `.env.example` a `.env` y configurar según entorno:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/academic_points

# JWT
JWT_SECRET=tu-clave-secreta-cambiar-en-produccion-minimo-32-caracteres
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# NCT (Nodo Coordinador)
NCT_BASE_URL=http://nct:5000

# Application
DEBUG=False
```

El archivo `docker-compose.yml` configura automáticamente estos valores para desarrollo.

## Limitaciones Conocidas y Seguridad

- **JWT Stateless:** El logout no invalida el token del lado del servidor (memset en producción)
- **Sin HTTPS:** Setup local solo. En producción usar Ingress con certificado TLS
- **Imágenes en BYTEA:** Almacenadas en PostgreSQL. En producción usar Cloud Storage
- **Sin firma ECDSA:** El backend acepta emisiones de ACADEMIC_SYSTEM sin validar emisor (usar firma en producción)

## Roadmap

- [ ] Integración con NCT para consultas en tiempo real
- [ ] Modal de creación/edición de productos
- [ ] Página de logs con filtros
- [ ] Visualización de blockchain (historial de bloques)
- [ ] Notificaciones push
- [ ] Exportación de historial (PDF)
- [ ] Autenticación 2FA
- [ ] Despliegue en Kubernetes + Google Cloud

---

**Documentación Relacionada:**
- [propuesta_profesores(1).md](propuesta_profesores(1).md) - Caso de uso y especificaciones
- [sistema_frontend_backend_bd.md](sistema_frontend_backend_bd.md) - Diseño técnico detallado