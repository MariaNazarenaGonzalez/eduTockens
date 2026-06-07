-- TODO: Create the PostgreSQL schema for roles, users, products, purchases and seed any initial data.

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    legajo VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role_id INTEGER REFERENCES roles(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price_points INTEGER NOT NULL,
    stock INTEGER,
    active BOOLEAN DEFAULT TRUE,
    image_data BYTEA,
    image_mime_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchases (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    points_spent INTEGER NOT NULL,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    nct_transaction_id VARCHAR(100)
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_users_legajo ON users(legajo);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON purchases(user_id);
CREATE INDEX IF NOT EXISTS idx_purchases_product_id ON purchases(product_id);

-- Insert default roles
INSERT INTO roles (name) VALUES ('student') ON CONFLICT DO NOTHING;
INSERT INTO roles (name) VALUES ('admin') ON CONFLICT DO NOTHING;
INSERT INTO roles (name) VALUES ('vendor') ON CONFLICT DO NOTHING;