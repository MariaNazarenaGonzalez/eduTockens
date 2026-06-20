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
- **`frontend/pages/login.html`** - Formulario de login por desafío firmado con clave privada. Almacena JWT en localStorage.
- **`frontend/pages/register.html`** - Formulario de registro para nuevos estudiantes con clave pública y validación de firma.

#### Dashboard de Estudiante
- **`frontend/pages/home.html`** - Homepage del estudiante con balance en blockchain, métricas (ganados/gastados/transacciones) e historial reciente.
- **`frontend/pages/marketplace.html`** - Grilla de productos disponibles con precios en puntos. Filtro de categorías y navegación a compra.
- **`frontend/pages/purchase.html`** - Confirmación de compra con detalle del producto, cálculo de saldo restante y validación.
- **`frontend/pages/profile.html`** - Perfil del estudiante con datos, identificador en blockchain y estadísticas.

#### Panel de Administración
- **`frontend/pages/admin.html`** - Dashboard admin con estadísticas globales, tabs para emisión de puntos y gestión de productos.

### Scripts JavaScript

#### Autenticación y Criptografía
- **`frontend/js/auth.js`** - Funciones para login, register, logout, gestión de tokens JWT y validación de autenticación.
- **`frontend/js/crypto-auth.js`** - Wrapper para generación de claves y firmas Ed25519 usando `@noble/curves` (vía CDN ESM).
- **`frontend/js/wallet-crypto.js`** - Cifrado y descifrado local (AES-GCM con PBKDF2) de la clave privada Ed25519 basándose en la contraseña.
- **`frontend/js/tx-signer.js`** - Replicación en JavaScript de la serialización del NCT para calcular y firmar `tx_id`.

#### Lógica de Páginas
- **`frontend/js/home.js`** - Carga de balance desde NCT, historial de transacciones, actualización de métricas del dashboard.
- **`frontend/js/marketplace.js`** - Carga de productos disponibles, renderizado de grid, navegación a compra.
- **`frontend/js/purchase.js`** - Confirmación de compra, validación de saldo, firma de transacción SPEND en cliente.
- **`frontend/js/admin.js`** - Emisión de puntos (EARN), gestión de productos, creación de vendors y carga de estadísticas.

## Estructura del Backend

### Configuración y Criptografía (`backend/core/`)
- **`config.py`** - Configuración de aplicación desde variables de entorno (DATABASE_URL, JWT_SECRET, NCT_BASE_URL, etc.).
- **`database.py`** - Configuración de SQLAlchemy async engine, session maker, Base ORM, función init_db().
- **`security.py`** - Funciones de autenticación JWT, desafíos de timestamp stateless y verificación de firma: create_access_token(), verify_token(), get_current_user().
- **`crypto.py`** - Operaciones Ed25519: firmar, verificar, generar keypair y calcular `tx_id` compatible con el NCT.

### Modelos ORM (`backend/models/`)
- **`models.py`** - Modelos SQLAlchemy para: Role, User (legajo, name, email, public_key, password_hash), Vendor (name, public_key), Product (name, price_points, stock, image_data, vendor_id), Purchase (user_id, product_id, points_spent, nct_transaction_id), TransactionLog (tx_type, counterparty_pubkey, amount, concept, nct_tx_id).

### Esquemas Pydantic (`backend/schemas/`)
- **`schemas.py`** - Esquemas de validación para requests/responses: UserRegister, UserLogin, TokenResponse, ProductCreate/Update, PurchaseCreate, EarnRequest, AdminStats, VendorCreate, VendorResponse, PurchaseLogResponse.

### Routers API (`backend/routers/`)
- **`auth.py`** - Endpoints: GET /auth/challenge, POST /auth/register, POST /auth/login, POST /auth/logout.
- **`users.py`** - Endpoint: GET /users/me (obtener perfil del usuario autenticado).
- **`products.py`** - Endpoints: GET /products, GET /products/{id} (incluye vendor_pubkey), GET /products/{id}/image.
- **`purchases.py`** - Endpoints: POST /purchases (reenvío de SPEND firmado client-side), GET /purchases/me.
- **`admin.py`** - Endpoints: POST /admin/earn, GET /admin/stats, GET/POST/PUT/DELETE /admin/products, POST/GET /admin/vendors (gestión de vendedores), GET /admin/purchases (historial de compras del sistema).
- **`students.py`** - Endpoints: GET /students/{legajo}/balance (obtiene balance + nonce del NCT), GET /students/{legajo}/transactions (lee log local de transacciones).

### Servicios (`backend/services/`)
- **`nct_client.py`** - Cliente HTTP para NCT: get_balance(), get_account() (nonce), get_chain(), emit_earn() (firmado por el backend), submit_signed_spend() (reenvío de firma cliente).

### Base de Datos (`db/`)
- **`init.sql`** - Script de inicialización con tablas: roles, users, vendors, products, purchases, transactions_log e índices.

## Flujo de Uso

### Estudiante
1. **Registro** (`pages/register.html`) - Crear cuenta con legajo, nombre, email, contraseña y clave pública. Se genera el par de claves Ed25519 y la clave privada se cifra con PBKDF2/AES-GCM localmente.
2. **Login** (`pages/login.html`) - Descifrar localmente la clave privada con la contraseña, firmar el desafío de timestamp del servidor y recibir JWT.
3. **Dashboard** (`pages/home.html`) - Ver saldo confirmado (desde NCT), historial local de transacciones y estadísticas.
4. **Marketplace** (`pages/marketplace.html`) - Explorar productos disponibles.
5. **Compra** (`pages/purchase.html`) - Confirmar compra, descifrar localmente la clave privada, construir y firmar la transacción SPEND, y enviarla al backend (que la reenvía al NCT).
6. **Perfil** (`pages/profile.html`) - Ver datos, identificador en blockchain y estadísticas.

### Administrador
1. **Login** (`pages/login.html`) - Autenticarse como admin firmando el desafío con su clave privada
2. **Dashboard** (`pages/admin.html`) - Ver estadísticas globales
3. **Emisión de Puntos** - Emitir EARN a estudiantes por actividades académicas
4. **Gestión de Productos** - Crear, editar, eliminar productos del marketplace

## Integración Backend

El frontend se comunica con el backend a través de una API REST en `http://localhost:8000/api`. Endpoints principales:

**Autenticación:**
- `POST /auth/register` - Registrar estudiante
- `POST /auth/login` - Login y obtener JWT
- `GET /auth/challenge` - Obtener desafío actual del servidor

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
- **Clave pública + firma ECDSA** - Registro y login por desafío firmado
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
NCT_BASE_URL=http://nct:8080

# Criptografía Autoridad Académica (Ed25519 en formato hex)
ACADEMIC_AUTHORITY_PRIVATE_KEY=20139855d1c596f918cdbefa75108b469fcd96e9c597b014385ab9b33e7503f7
ACADEMIC_AUTHORITY_PUBLIC_KEY=4bda9548d161d7edf80fc1ac34a09e4c609db55bfa5a58fe44c000ddae936a74
AUTH_CHALLENGE_WINDOW_SECONDS=60

# Application
DEBUG=False
```

El archivo `docker-compose.yml` configura automáticamente estos valores para desarrollo.

## Limitaciones Conocidas y Seguridad

- **JWT Stateless:** El logout no invalida el token del lado del servidor (memset en producción)
- **Sin HTTPS:** Setup local solo. En producción usar Ingress con certificado TLS
- **Imágenes en BYTEA:** Almacenadas en PostgreSQL. En producción usar Cloud Storage
- **Clave admin de desarrollo:** El seed inicial incluye una clave pública de ejemplo; reemplazarla en entornos compartidos o productivos

## Roadmap

- [x] Integración con NCT para consultas en tiempo real y transacciones firmadas
- [x] Modal de creación/edición de productos
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

## Notas de cambios

- 2026-06-19: Integración criptográfica completa con Ed25519 (64 caracteres hex) compatible con el NCT, reemplazando ECDSA P-384. Implementación de cifrado local de clave privada del estudiante con PBKDF2/AES-GCM (Wallet). Nueva entidad/tabla de `vendors` y logs locales (`transactions_log`).
- 2026-06-09: Se añadió el router `students` con endpoints `GET /students/{legajo}/balance` y `GET /students/{legajo}/transactions` para consulta de saldo e historial a través del backend.
- 2026-06-09: Corregido comportamiento de redirección 307 en `GET /products` (ahora acepta la ruta sin slash), evitando que proxies/servidores frontales impidieran la carga desde el frontend.
