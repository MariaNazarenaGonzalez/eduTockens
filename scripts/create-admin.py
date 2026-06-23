# DEO GLORIA

"""Crear una cuenta de administrador.

Uso:
    docker compose exec backend python scripts/create-admin.py \
        --legajo admin2 \
        --name "María Gómez" \
        --email maria@unlu.edu.ar \
        --password "contraseña-segura"

    # Por defecto usa AUTHORITY_PUBLIC_KEY del entorno como public_key del admin.
    # Si pasás --public-key, se usa esa en su lugar (modo no-custodial / dev).

Qué hace:
    1. Usa AUTHORITY_PUBLIC_KEY (o --public-key) como clave pública del admin.
    2. Hashea la contraseña con bcrypt.
    3. Inserta el admin en la DB con role='admin'.
    4. Muestra los datos de la cuenta.

Wallet custodial — la clave privada del admin es AUTHORITY_PRIVATE_KEY,
que vive en el backend (Secret de Kubernetes). El admin se autentica con
legajo + contraseña; el backend firma el challenge por él.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# ── Bcrypt (mismo algoritmo que el backend — bcrypt directo, no passlib) ──
try:
    import bcrypt
    def _hash(password: str) -> str:
        """Hashea password con bcrypt. Idéntico a backend/core/security.py:hash_password."""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
except ImportError:
    print("ERROR: bcrypt no instalado. Ejecutá: pip install bcrypt")
    sys.exit(1)

# ── Ed25519 ──────────────────────────────────────────────────────
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:
    print("ERROR: cryptography no instalado. Ejecutá: pip install cryptography")
    sys.exit(1)


def _generate_keypair() -> tuple[str, str]:
    """Devuelve (private_key_hex, public_key_hex)."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    return (
        priv.private_bytes_raw().hex(),
        pub.public_bytes_raw().hex(),
    )


# ── DB ───────────────────────────────────────────────────────────
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/academic_points",
)

_engine = create_async_engine(DATABASE_URL)
_SessionLocal = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _create_admin(
    legajo: str,
    name: str,
    email: str,
    password: str,
    public_key: str,
) -> None:
    async with _SessionLocal() as db:
        # Validar que el legajo no exista
        result = await db.execute(
            text("SELECT id FROM users WHERE legajo = :legajo"),
            {"legajo": legajo},
        )
        if result.fetchone():
            print(f"ERROR: Ya existe un usuario con legajo '{legajo}'")
            sys.exit(2)

        # Obtener role_id de 'admin'
        result = await db.execute(
            text("SELECT id FROM roles WHERE name = 'admin'"),
        )
        row = result.fetchone()
        if not row:
            print("ERROR: El rol 'admin' no existe en la DB. ¿Corriste init.sql?")
            sys.exit(3)

        role_id = row[0]
        password_hash = _hash(password)

        await db.execute(
            text(
                "INSERT INTO users (legajo, name, email, public_key, password_hash, role_id) "
                "VALUES (:legajo, :name, :email, :public_key, :password_hash, :role_id)"
            ),
            {
                "legajo": legajo,
                "name": name,
                "email": email,
                "public_key": public_key,
                "password_hash": password_hash,
                "role_id": role_id,
            },
        )
        await db.commit()

    print(f"✅ Admin '{legajo}' creado.\n")
    print("─────────────── DATOS DE LA WALLET DEL ADMIN ───────────────")
    print()
    print("  Estas credenciales son SOLO para autenticación (login).")
    print("  La clave que firma EARN es la institucional (AUTHORITY_PRIVATE_KEY).")
    print()
    print(f"  Legajo:     {legajo}")
    print(f"  Email:      {email}")
    print(f"  Password:   {password}")
    print(f"  Public Key: {public_key}")
    print()
    print("──────────────────────────────────────────────────────────────")
    print()
    print("Para que el admin pueda loguearse, generá su wallet en el navegador:")
    print()
    print(f"  1. Abrí la consola del navegador en la página de login.")
    print(f"  2. Ejecutá:")
    print(f"     const kp = await EduWallet.generateKeypair();")
    print(f"     // kp.publicKeyHex debe ser: {public_key}")
    print(f"     await EduWallet.storePrivateKey('{legajo}', kp.privateKeyHex, '{password}');")
    print()
    print("  3. Iniciá sesión normalmente en /login.")


# ── Main ─────────────────────────────────────────────────────────
async def main() -> None:
    parser = argparse.ArgumentParser(description="Crear una cuenta de administrador")
    parser.add_argument("--legajo", required=True, help="Legajo (identificador único)")
    parser.add_argument("--name", required=True, help="Nombre completo")
    parser.add_argument("--email", required=True, help="Email institucional")
    parser.add_argument("--password", required=True, help="Contraseña (mín. 8 chars)")
    parser.add_argument("--public-key", help="Clave pública Ed25519 (64 hex). Si no se pasa, se genera una nueva.")

    args = parser.parse_args()

    if len(args.password) < 8:
        print("ERROR: La contraseña debe tener al menos 8 caracteres")
        sys.exit(1)

    if args.public_key:
        public_key = args.public_key.strip().lower()
        if len(public_key) != 64 or not all(c in "0123456789abcdef" for c in public_key):
            print("ERROR: --public-key debe ser 64 caracteres hex")
            sys.exit(1)
    else:
        # Modo custodial: usar la clave institucional (AUTHORITY_PUBLIC_KEY).
        # La clave privada (AUTHORITY_PRIVATE_KEY) vive en el backend y firma
        # el challenge durante el login del admin automáticamente.
        public_key = os.getenv("AUTHORITY_PUBLIC_KEY", "")
        if not public_key:
            print("ERROR: AUTHORITY_PUBLIC_KEY no está definida en el entorno.")
            print("  Pasá --public-key, o asegurate de que la variable esté seteada.")
            sys.exit(1)
        if len(public_key) != 64 or not all(c in "0123456789abcdef" for c in public_key):
            print(f"ERROR: AUTHORITY_PUBLIC_KEY={public_key} no es 64 hex válida")
            sys.exit(1)

    await _create_admin(
        legajo=args.legajo.strip(),
        name=args.name.strip(),
        email=args.email.strip(),
        password=args.password,
        public_key=public_key,
    )


if __name__ == "__main__":
    asyncio.run(main())
