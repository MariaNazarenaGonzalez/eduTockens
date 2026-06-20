# Sistema de Aplicación Web — Puntos Académicos sobre Blockchain

**TP Integrador — Blockchain Distribuida y CUDA**
Documento de diseño: capa de aplicación (Frontend, Backend, Base de Datos)

---

## 1. Visión general

Este documento describe la capa de aplicación que opera por encima de la infraestructura blockchain del trabajo integrador. Dicha infraestructura está compuesta por el Nodo Coordinador de Transacciones (NCT), la pool de workers GPU, RabbitMQ y Redis, y no es objeto de este documento.

La capa de aplicación consta de tres componentes:

- **Frontend:** interfaz web estática (HTML, CSS, JavaScript)
- **Backend:** API REST (Python con FastAPI)
- **Base de datos:** PostgreSQL

El backend es el único punto de contacto con el NCT. El frontend nunca se comunica directamente con la blockchain.

---

## 2. Actores del sistema

| Actor | Descripción |
|---|---|
| **Estudiante** | Usuario registrado que acumula y gasta puntos académicos. |
| **Administrador** | Usuario con rol `admin` que emite puntos y gestiona productos. |
| **Sistema Académico (NCT)** | Infraestructura blockchain que procesa y confirma transacciones. |

---

## 3. Frontend

### 3.1 Stack tecnológico

HTML5, CSS3 y JavaScript vanilla. Sin frameworks ni herramientas de build. Los archivos son servidos como contenido estático por un servidor Nginx dentro de Docker.

### 3.2 Pantallas

#### Homepage público (`/`)
Pantalla de entrada al sistema. Describe el propósito del sistema de puntos académicos. El header incluye un enlace a la pantalla de login. No requiere autenticación.

#### Login (`/login`)
Formulario con legajo/email, contraseña, desafío del sistema, desafío firmado y clave privada (opcional). La clave privada Ed25519 del usuario se almacena cifrada localmente. Al iniciar sesión, la clave se descifra localmente con la contraseña provista para firmar el desafío. Al autenticarse correctamente contra el backend (quien valida la firma con la clave pública almacenada y verifica la contraseña), devuelve un JWT que el frontend almacena en `localStorage` (sesión activa). La redirección post-login depende del rol:
- `student` → Homepage de estudiante
- `admin` → Panel de administración

#### Register (`/register`)
Formulario de registro para nuevos estudiantes. Campos: legajo, nombre completo, email, contraseña, clave pública, desafío del sistema, desafío firmado y clave privada. Incluye una acción para generar un par de claves Ed25519 de forma local utilizando `@noble/curves`. La clave privada generada se cifra localmente mediante AES-GCM (derivando la clave con PBKDF2) utilizando la contraseña del estudiante y se almacena en `localStorage` bajo `walletCipher:{legajo}`. Solo la clave pública y el hash de la contraseña se envían al backend durante el registro. Solo disponible para el rol `student`; los administradores son creados directamente en la base de datos (seed).

#### Homepage de estudiante (`/home`)
Pantalla principal del estudiante autenticado. Muestra:
- Saldo actual de puntos confirmados (consultado al NCT vía backend)
- Historial unificado de transacciones EARN y SPEND con fecha, concepto y monto
- Acceso al marketplace

#### Marketplace (`/marketplace`)
Grilla de productos disponibles con nombre, descripción y precio en puntos. Cada producto tiene un botón para iniciar la compra. Incluye navegación de regreso al homepage de estudiante.

#### Compra (`/purchase/:id`)
Pantalla de confirmación de compra para un producto específico. Muestra el detalle del producto y el costo en puntos. Al confirmar, el backend emite la transacción SPEND al NCT. El resultado se presenta mediante un diálogo popup:
- **Éxito:** confirmación de compra con botón para volver al marketplace
- **Saldo insuficiente:** mensaje de error con botón para volver al marketplace

#### Panel de administración (`/admin`)
Exclusivo para usuarios con rol `admin`. Contiene cuatro secciones/pestañas principales:

**Emisión de puntos:** formulario para otorgar puntos a un estudiante. Campos: legajo del estudiante, cantidad de puntos y concepto (ej: `PARCIAL1`, `ASISTENCIA_2026-06-05`). Al enviar, el backend construye la transacción EARN, la firma digitalmente con la clave privada de la autoridad académica y la transmite al NCT.

**Gestión de productos:** permite dar de alta y listar productos disponibles:
- **Añadir producto:** formulario con campos: nombre, descripción, precio en puntos, stock (campo opcional; vacío implica ilimitado) y selector de vendor asociado (de la lista de vendors). La petición se envía como JSON al backend.
- **Eliminar producto:** botón para eliminar físicamente el producto de la base de datos local (mediante petición HTTP DELETE).

**Gestión de vendors:** formulario para dar de alta nuevos vendedores. Al enviar el nombre del vendor, el backend genera un par de claves Ed25519, descarta la clave privada inmediatamente, y almacena únicamente el nombre y la clave pública (dirección receptora pasiva) en la tabla `vendors`.

**Logs de auditoría:** tabla que muestra las últimas 30 compras realizadas en el sistema (legajo del estudiante, nombre del producto, puntos gastados, ID de transacción del NCT y fecha), consultadas de la base de datos local de eduTockens.

### 3.3 Manejo de autenticación en el frontend

El JWT recibido al hacer login se almacena en `localStorage` (bajo la clave `token`). Se incluye en el header `Authorization: Bearer <token>` en cada request al backend. Las rutas protegidas verifican la presencia del token antes de renderizar; si no existe, redirigen al login. Asimismo, la clave pública activa y la clave privada activa (temporalmente descifrada) se gestionan localmente en `localStorage` para autorizar operaciones y firmar transacciones SPEND de forma transparente.

---

## 4. Backend

### 4.1 Stack tecnológico

Python 3.11 con FastAPI. Dependencias principales:

- `fastapi` — framework web y documentación automática (Swagger en `/docs`)
- `uvicorn` — servidor ASGI
- `sqlalchemy` — ORM para PostgreSQL
- `asyncpg` — driver async para PostgreSQL
- `python-jose` — generación y validación de JWT
- `cryptography` — validación de firmas Ed25519 en registro, login y firma de transacciones EARN
- `httpx` — cliente HTTP async para comunicarse con el NCT
- `python-multipart` — soporte para recepción de archivos vía `multipart/form-data`

### 4.2 Responsabilidades

- Autenticar usuarios por desafio firmado y emitir JWT con información de rol
- Autenticar usuarios por desafío firmado y emitir JWT con información de rol
- Registrar nuevos estudiantes con clave pública validada por firma
- Proteger endpoints según rol (`student` o `admin`)
- Listar y gestionar productos del marketplace
- Recibir, almacenar y servir imágenes de productos
- Procesar compras: validar existencia del producto y emitir transacción SPEND al NCT
- Emitir puntos a estudiantes desde el panel admin enviando transacciones EARN al NCT
- Consultar saldo e historial 

### 4.3 Endpoints

#### Autenticación

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/auth/register` | Registrar nuevo estudiante |
| `POST` | `/auth/login` | Login, devuelve JWT |
| `GET` | `/auth/challenge` | Desafío de timestamp stateless del servidor para firmar |
| `POST` | `/auth/logout` | Logout (descarte del token en el cliente) |

> **Nota:** el logout es stateless. El backend no invalida el JWT del lado del servidor; el cliente descarta el token localmente. Esto se documenta como limitación conocida, consistente con el alcance del proyecto.

#### Usuarios

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/users/me` | Perfil del usuario autenticado |

#### Saldo e historial (delega al NCT)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/students/{legajo}/balance` | Saldo confirmado y nonce actual del estudiante (desde el NCT) |
| `GET` | `/students/{legajo}/transactions` | Historial de transacciones EARN y SPEND (desde el log local) |

#### Marketplace y productos

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/products` | Listar productos activos |
| `GET` | `/products/{id}` | Detalle de un producto (incluye `vendor_pubkey`) |
| `GET` | `/products/{id}/image` | Servir la imagen del producto (devuelve binario con `Content-Type` correcto) |

#### Compras

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/purchases` | Procesar compra; recibe la transacción SPEND firmada en cliente, la valida y reenvía al NCT |
| `GET` | `/purchases/me` | Historial de compras del estudiante autenticado |

#### Administración (requieren rol `admin`)

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/admin/earn` | Emitir puntos a un estudiante, firma y emite EARN al NCT |
| `GET` | `/admin/stats` | Obtener estadísticas del sistema |
| `GET` | `/admin/products` | Listar todos los productos (activos e inactivos) |
| `POST` | `/admin/products` | Crear producto (recibe JSON body) |
| `PUT` | `/admin/products/{id}` | Editar producto (recibe JSON body) |
| `DELETE` | `/admin/products/{id}` | Eliminar físicamente un producto |
| `POST` | `/admin/vendors` | Crear un vendor (genera Ed25519 y descarta la privada inmediatamente) |
| `GET` | `/admin/vendors` | Listar todos los vendors |
| `GET` | `/admin/purchases` | Listar las últimas 30 compras del sistema |

### 4.4 Comunicación con el NCT

El backend actúa como cliente HTTP del NCT. Toda transacción EARN es construida, firmada con la clave privada de la autoridad académica (`ACADEMIC_AUTHORITY_PRIVATE_KEY`) y enviada al NCT. Las transacciones SPEND son construidas y firmadas en el cliente (frontend) y el backend solo las reenvía de forma transparente. Las consultas de saldo y nonce se delegan al NCT, mientras que el historial de transacciones se sirve desde la base de datos local utilizando la tabla cacheada `transactions_log`.

El NCT nunca es contactado directamente por el frontend.

---

## 5. Base de datos

### 5.1 Motor

PostgreSQL 15.

### 5.2 Esquema

#### Tabla `roles`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | Identificador |
| `name` | `VARCHAR(50) UNIQUE NOT NULL` | Nombre del rol (`student`, `admin`) |

#### Tabla `users`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | Identificador interno |
| `legajo` | `VARCHAR(20) UNIQUE NOT NULL` | Legajo universitario del estudiante |
| `name` | `VARCHAR(100) NOT NULL` | Nombre completo |
| `email` | `VARCHAR(150) UNIQUE NOT NULL` | Email |
| `public_key` | `VARCHAR(64) UNIQUE NOT NULL` | Clave pública Ed25519 (64 caracteres hex) |
| `password_hash` | `VARCHAR(60) NOT NULL` | Hash bcrypt de la contraseña |
| `role_id` | `INTEGER REFERENCES roles(id)` | Rol del usuario |
| `created_at` | `TIMESTAMP DEFAULT NOW()` | Fecha de registro |

#### Tabla `vendors`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | Identificador del vendor |
| `name` | `VARCHAR(100) NOT NULL` | Nombre comercial del vendedor |
| `public_key` | `VARCHAR(64) UNIQUE NOT NULL` | Clave pública Ed25519 (64 caracteres hex) |
| `created_at` | `TIMESTAMP DEFAULT NOW()` | Fecha de creación |

#### Tabla `products`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | Identificador |
| `name` | `VARCHAR(100) NOT NULL` | Nombre del producto |
| `description` | `TEXT` | Descripción |
| `price_points` | `INTEGER NOT NULL` | Precio en puntos |
| `stock` | `INTEGER` | Stock disponible (`NULL` = ilimitado) |
| `active` | `BOOLEAN DEFAULT TRUE` | Visible en el marketplace |
| `image_data` | `BYTEA` | Binario de la imagen del producto (`NULL` si no se cargó imagen) |
| `image_mime_type` | `VARCHAR(50)` | Tipo MIME de la imagen (ej: `image/jpeg`, `image/png`) |
| `vendor_id` | `INTEGER REFERENCES vendors(id)` | Referencia al vendedor del producto |
| `created_at` | `TIMESTAMP DEFAULT NOW()` | Fecha de creación |

> **Almacenamiento de imágenes:** la imagen se guarda directamente en PostgreSQL como `BYTEA`. El endpoint `GET /products/{id}/image` lee el binario y lo sirve con el header `Content-Type` correspondiente al valor de `image_mime_type`. Este enfoque mantiene toda la información del producto en un único sistema de persistencia, eliminando la necesidad de un volumen de archivos separado y simplificando el backup del sistema. Para imágenes grandes o alta concurrencia en producción, se reemplazaría por un bucket en Google Cloud Storage.

#### Tabla `purchases`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | Identificador |
| `user_id` | `INTEGER REFERENCES users(id)` | Estudiante que realizó la compra |
| `product_id` | `INTEGER REFERENCES products(id)` | Producto comprado |
| `points_spent` | `INTEGER NOT NULL` | Puntos gastados al momento de la compra |
| `purchased_at` | `TIMESTAMP DEFAULT NOW()` | Timestamp de la compra |
| `nct_transaction_id` | `VARCHAR(100)` | ID de la transacción SPEND confirmada en el NCT |

> **`nct_transaction_id`** es la columna clave para auditoría: permite cruzar cada compra registrada en PostgreSQL con su transacción SPEND correspondiente en la blockchain.

#### Tabla `transactions_log`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | Identificador |
| `user_id` | `INTEGER REFERENCES users(id)` | Estudiante relacionado |
| `tx_type` | `VARCHAR(10) NOT NULL` | Tipo de transacción (`EARN` o `SPEND`) |
| `counterparty_pubkey` | `VARCHAR(64) NOT NULL` | Clave pública de la contraparte (vendedor en SPEND, autoridad en EARN) |
| `amount` | `INTEGER NOT NULL` | Monto de la transacción |
| `concept` | `VARCHAR(128) NOT NULL` | Concepto de la transacción |
| `nct_tx_id` | `VARCHAR(100)` | ID de la transacción confirmada en el NCT |
| `created_at` | `TIMESTAMP DEFAULT NOW()` | Fecha de registro |

### 5.3 Fuente de verdad

PostgreSQL es la fuente de verdad para usuarios y productos. La blockchain (vía NCT y Redis) es la fuente de verdad para saldos e historial de transacciones. La tabla `purchases` actúa como puente de trazabilidad entre ambas.

---

## 6. Docker

### 6.1 Estructura de servicios

El proyecto define tres servicios en Docker Compose:

- `frontend` — Nginx sirviendo los archivos estáticos
- `backend` — FastAPI corriendo con Uvicorn
- `db` — PostgreSQL

## Notas de cambios

- 2026-06-19: Migración a firmas criptográficas Ed25519 (hexadecimal de 64 caracteres) para compatibilidad nativa con la blockchain del NCT. Cifrado local de clave privada de estudiantes (AES-GCM/PBKDF2) y almacenamiento en `localStorage`. Creación de entidad `vendors` y del registro local de transacciones (`transactions_log`).
- 2026-06-09: Se añadió el router `students` con endpoints `GET /students/{legajo}/balance` y `GET /students/{legajo}/transactions` para que el frontend consulte saldo e historial a través del backend.
- 2026-06-09: Corregido el problema de redirección 307 en `GET /products` (acepta la ruta sin slash), lo que solucionó fallos de carga en el `marketplace` desde el frontend detrás de proxies.

### 6.2 `docker-compose.yml`

```yaml
version: "3.9"

services:

  frontend:
    build:
      context: ./frontend
    ports:
      - "8090:80"
    depends_on:
      - backend

  backend:
    build:
      context: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/academic_points
      NCT_BASE_URL: http://host.docker.internal:NCT_PORT  # ajustar según red del NCT
      JWT_SECRET: change_this_in_production
      JWT_ALGORITHM: HS256
      JWT_EXPIRE_MINUTES: 60
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: academic_points
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### 6.3 Dockerfile — Frontend

```dockerfile
FROM nginx:alpine
COPY . /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

`nginx.conf` mínimo para SPA con rutas del lado del cliente:

```nginx
server {
    listen 80;

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000/;
        client_max_body_size 5M;  # permite subir imágenes de hasta 5 MB
    }
}
```

### 6.4 Dockerfile — Backend

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.5 Estructura de directorios del proyecto

```
proyecto/
├── docker-compose.yml
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── index.html
│   ├── pages/
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── home.html
│   │   ├── marketplace.html
│   │   ├── purchase.html
│   │   └── admin.html
│   ├── css/
│   │   └── styles.css
│   └── js/
│       ├── auth.js
│       ├── crypto-auth.js
│       ├── wallet-crypto.js
│       ├── tx-signer.js
│       ├── marketplace.js
│       ├── home.js
│       ├── purchase.js
│       └── admin.js
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── products.py
│   │   ├── purchases.py
│   │   ├── admin.py
│   │   └── students.py
│   ├── models/
│   │   └── models.py
│   ├── schemas/
│   │   └── schemas.py
│   ├── services/
│   │   └── nct_client.py
│   └── core/
│       ├── config.py
│       ├── crypto.py
│       ├── database.py
│       └── security.py
└── db/
    └── init.sql
```

### 6.6 Comandos para pruebas locales

```bash
# Levantar el proyecto
docker compose up --build

# Levantar en segundo plano
docker compose up --build -d

# Ver logs del backend
docker compose logs -f backend

# Detener y eliminar contenedores
docker compose down

# Eliminar también el volumen de PostgreSQL (reset completo)
docker compose down -v
```

La documentación interactiva de la API queda disponible en `http://localhost:8000/docs` una vez levantado el proyecto.

---

## 7. Consideraciones de seguridad documentadas

Las siguientes son limitaciones conocidas, aceptadas por el alcance universitario del proyecto y documentadas para el informe:

- **JWT stateless:** el logout no invalida el token del lado del servidor. En producción se usaría una lista negra de tokens en Redis o sesiones con estado.
- **Almacenamiento de clave privada en localStorage (cifrado):** Aunque la clave privada Ed25519 del estudiante ahora se almacena cifrada mediante AES-GCM (derivando la clave con PBKDF2) utilizando la contraseña del estudiante, el almacenamiento en `localStorage` sigue expuesto a posibles ataques de Cross-Site Scripting (XSS). En producción se aconseja utilizar la WebCrypto API con claves no-extraíbles o billeteras externas.
- **Credenciales en variables de entorno:** el `docker-compose.yml` incluye credenciales en texto plano. En producción se utilizarían secrets de Kubernetes o un gestor de secretos dedicado.
- **Sin HTTPS:** el setup de Docker local no configura TLS. En el despliegue en Google Cloud se gestionaría mediante un Ingress con certificado administrado.
- **Imágenes almacenadas como BYTEA:** no se valida el contenido del archivo más allá del MIME type declarado por el cliente. En producción se agregaría validación del magic number del archivo y un límite de tamaño estricto en el backend.

---

## 8. Roadmap hacia Kubernetes en Google Cloud

El `docker-compose.yml` definido en este documento es el punto de partida para el despliegue en GKE. La migración implica:

- Un `Deployment` por cada servicio (`frontend`, `backend`)
- Un `StatefulSet` para PostgreSQL o reemplazo por Cloud SQL
- `ConfigMap` para variables de entorno no sensibles
- `Secret` para credenciales y JWT secret
- `Ingress` con certificado TLS administrado por Google
- `HorizontalPodAutoscaler` para el backend si se requiere escala bajo carga
- Migración del almacenamiento de imágenes de `BYTEA` en PostgreSQL a un bucket en Google Cloud Storage, sirviendo las imágenes mediante URL firmadas o CDN

Esta migración está fuera del alcance de la entrega actual y se documenta como trabajo futuro.

---

## 9. Referencias

- FastAPI documentation — https://fastapi.tiangolo.com
- SQLAlchemy async — https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Docker Compose specification — https://docs.docker.com/compose/compose-file/
- Propuesta de caso de uso blockchain — `propuesta_profesores(1).md`
