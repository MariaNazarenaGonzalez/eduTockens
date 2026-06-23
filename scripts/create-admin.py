# DEO GLORIA

"""Crear una cuenta de administrador.

Uso:
    docker compose exec backend python scripts/create-admin.py \
        --legajo admin2 \
        --name "María Gómez" \
        --email maria@unlu.edu.ar \
        --password "contraseña-segura"

    # Si no pasás --public-key, se genera un par Ed25519 nuevo y
    # se muestra la clave privada UNA SOLA VEZ (guardala en tu wallet).

Qué hace:
    1. Genera un keypair Ed25519 (o usa el --public-key dado).
    2. Hashea la contraseña con bcrypt.
    3. Inserta el admin en la DB con role='admin'.
    4. Muestra los datos para configurar la wallet del admin en el navegador.

La clave privada del admin es SOLO para autenticación (challenge+firma).
NO es la clave institucional que firma EARN — esa vive en AUTHORITY_PRIVATE_KEY.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# ── Bcrypt (mismo algoritmo que el backend) ──────────────────────
try:
    from passlib.context import CryptContext
    _pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    def _hash(password: str) -> str:
        return _pwd.hash(password)
except ImportError:
    print("ERROR: passlib no instalado. Ejecutá: pip install passlib[bcrypt]")
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

    private_key = None
    if args.public_key:
        public_key = args.public_key.strip().lower()
        if len(public_key) != 64 or not all(c in "0123456789abcdef" for c in public_key):
            print("ERROR: --public-key debe ser 64 caracteres hex")
            sys.exit(1)
    else:
        private_key, public_key = _generate_keypair()

    await _create_admin(
        legajo=args.legajo.strip(),
        name=args.name.strip(),
        email=args.email.strip(),
        password=args.password,
        public_key=public_key,
    )

    if private_key:
        print(f"\n⚠️  GUARDÁ esta clave privada. Solo se muestra UNA VEZ:")
        print(f"   Private Key: {private_key}")


if __name__ == "__main__":
    asyncio.run(main())
