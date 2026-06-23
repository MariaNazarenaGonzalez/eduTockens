-- DEO GLORIA

-- ============================================================================
-- eduTockens — Schema PostgreSQL
-- Migración: autenticación por challenge firmado con Ed25519 (sin password).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- roles
-- Solo dos roles de USUARIO (login). 'vendor' NO es un rol de usuario:
-- los vendors son una entidad propia (ver tabla `vendors`) que nunca hace
-- login ni firma transacciones — solo recibe SPEND de forma pasiva.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

INSERT INTO roles (name) VALUES ('student') ON CONFLICT DO NOTHING;
INSERT INTO roles (name) VALUES ('admin') ON CONFLICT DO NOTHING;

-- ----------------------------------------------------------------------------
-- users
-- Auth de DOS FACTORES:
--   1. Firma Ed25519 del challenge (prueba de posesión de la clave privada).
--   2. Password tradicional (bcrypt) — el MISMO password que el usuario usa
--      para cifrar su clave privada en localStorage del lado del cliente.
-- public_key: 64 caracteres hex lowercase (clave pública Ed25519 raw, 32 bytes).
-- password_hash: hash bcrypt (60 chars, formato $2b$...).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    legajo VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    public_key VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(60) NOT NULL,
    role_id INTEGER REFERENCES roles(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_users_public_key_hex
        CHECK (public_key ~ '^[0-9a-f]{64}$')
);

-- ----------------------------------------------------------------------------
-- vendors  (NUEVA TABLA)
-- Un vendor es solo una clave pública receptora de SPEND ("burn address" —
-- nadie firma en su nombre; el backend genera el keypair al crear el vendor
-- y descarta la clave privada inmediatamente, solo persiste la pública).
-- Creado por el admin. No es un usuario, no hace login.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vendors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    public_key VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_vendors_public_key_hex
        CHECK (public_key ~ '^[0-9a-f]{64}$')
);

-- ----------------------------------------------------------------------------
-- products
-- + vendor_id: a qué vendor pertenece (receiver_pubkey de la SPEND).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price_points INTEGER NOT NULL,
    stock INTEGER,
    active BOOLEAN DEFAULT TRUE,
    image_data BYTEA,
    image_mime_type VARCHAR(50),
    vendor_id INTEGER REFERENCES vendors(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- purchases
-- Sin cambios de esquema. nct_transaction_id sigue siendo el cruce de
-- auditoría entre la compra en Postgres y la transacción SPEND en el NCT.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchases (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    points_spent INTEGER NOT NULL,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    nct_transaction_id VARCHAR(100)
);

-- ----------------------------------------------------------------------------
-- transactions_log  (NUEVA TABLA)
-- Índice local de TODAS las transacciones (EARN y SPEND) que el backend
-- emitió al NCT, indexado por estudiante, para servir
-- GET /students/{legajo}/transactions sin tener que leer /chain del NCT
-- en cada request. El NCT sigue siendo la fuente de verdad; esto es un
-- caché de lectura poblado en el momento en que el backend emite cada tx.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transactions_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    tx_type VARCHAR(10) NOT NULL,
    counterparty_pubkey VARCHAR(64) NOT NULL,
    amount INTEGER NOT NULL,
    concept VARCHAR(128) NOT NULL,
    nct_tx_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_transactions_log_tx_type
        CHECK (tx_type IN ('EARN', 'SPEND'))
);

-- Columna agregada (audit trail): qué admin disparó cada EARN.
-- NULL para SPEND (el estudiante firma su propia compra).
ALTER TABLE transactions_log
ADD COLUMN IF NOT EXISTS triggered_by_admin_id INTEGER REFERENCES users(id);

-- ----------------------------------------------------------------------------
-- Índices
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_users_legajo ON users(legajo);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_public_key ON users(public_key);
CREATE INDEX IF NOT EXISTS idx_vendors_public_key ON vendors(public_key);
CREATE INDEX IF NOT EXISTS idx_products_vendor_id ON products(vendor_id);
CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON purchases(user_id);
CREATE INDEX IF NOT EXISTS idx_purchases_product_id ON purchases(product_id);
CREATE INDEX IF NOT EXISTS idx_transactions_log_user_id ON transactions_log(user_id);

-- ----------------------------------------------------------------------------
-- Seed de desarrollo — Administrador
--
-- ATENCIÓN — REEMPLAZAR EN PRODUCCIÓN / EN CUALQUIER ENTORNO COMPARTIDO:
-- La clave pública de abajo es SOLO para autenticación del admin (challenge
-- firmado). NO es la clave institucional que firma EARN — esa vive en
-- CLAVE DISTINTAS: la del admin (autenticación) ≠ la institucional (firma EARN).
--
-- Par de desarrollo para AUTENTICACIÓN del admin:
--   private: 802c2f7080cf78f619a8856c408546ccbe3e3201e8f40c7b15c1d33fa5fb0f13
--   public:  a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2
--   Password: "admin123"
--   (generar uno real para cualquier entorno compartido)
--
-- Par INSTITUCIONAL (firma EARN) — NO está en esta tabla, vive en:
--   Kubernetes: Secret apps/backend-secret → AUTHORITY_PRIVATE_KEY
--   Docker:      backend/.env → AUTHORITY_PRIVATE_KEY
--   NCT:         AUTHORITY_PUBKEY (debe coincidir con la pubkey de arriba)
-- ----------------------------------------------------------------------------
-- INSERT INTO users (legajo, name, email, public_key, password_hash, role_id)
-- VALUES (
--     'admin',
--     'Administrador',
--     'admin@edutoken.com',
--     'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
--     '$2b$12$ajaa77ta/BLuedTF5bFfju.Uj9GaFQajXT8Hrxv8JZ2HuDnxfS762',
--     (SELECT id FROM roles WHERE name = 'admin')
-- ) ON CONFLICT DO NOTHING;
