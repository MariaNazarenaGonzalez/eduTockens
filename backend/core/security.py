# DEO GLORIA

"""Autenticación para eduTockens — challenge firmado con Ed25519, sin password.

Flujo:
    1. GET /auth/challenge   → backend devuelve el timestamp actual del
       servidor como string. NO se persiste en ningún lado (ni Redis ni
       Postgres) — es stateless por construcción.
    2. El cliente firma ese string tal cual (UTF-8 bytes) con su clave
       privada Ed25519.
    3. POST /auth/login o /auth/register → el cliente reenvía el mismo
       `challenge` junto con `signature`.
    4. El backend recalcula `now = time.time()` y exige:
           now - AUTH_CHALLENGE_WINDOW_SECONDS <= float(challenge) <= now
       Si el challenge es viejo (replay) o "del futuro" (reloj
       desincronizado / manipulación), se rechaza.
    5. Se verifica la firma Ed25519 de `challenge` con la public_key
       correspondiente (la del body en /register, la de la DB en /login).
    6. Si todo es válido, se emite un JWT (para login) o se crea el User
       (para register).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.crypto import CryptoError, verify_signature
from core.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


class AuthError(Exception):
    """Error de autenticación (challenge inválido, firma inválida, password incorrecto, etc.)."""


# ---------------------------------------------------------------------------
# Password — segundo factor de autenticación (bcrypt)
#
# Este es el MISMO password que el usuario usa para cifrar su clave privada
# Ed25519 en localStorage (ver frontend/js/wallet-crypto.js). El backend
# nunca ve la clave privada — solo valida este hash como factor adicional
# de "algo que sabés", complementando la firma Ed25519 ("algo que tenés").
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hashea `password` con bcrypt. Devuelve el hash como string (60 chars)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica `password` contra `password_hash` (bcrypt). No lanza excepción
    en caso de no coincidir — devuelve False.
    """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # password_hash mal formado — tratar como no coincidente, no como
        # error del servidor.
        return False


# ---------------------------------------------------------------------------
# Challenge — generación y validación de ventana de tiempo
# ---------------------------------------------------------------------------


def generate_challenge() -> str:
    """Genera el challenge: el timestamp actual del servidor en segundos
    enteros (sin decimales), como string.

    No se persiste. La validez se controla únicamente recalculando el
    "ahora" del servidor en el momento de la verificación y comparando
    contra la ventana permitida (ver `validate_challenge_window`).
    """
    return str(int(time.time()))


def validate_challenge_window(challenge: str) -> int:
    """Valida que `challenge` sea un timestamp (segundos enteros) dentro de
    la ventana permitida.

    Ventana: [now - AUTH_CHALLENGE_WINDOW_SECONDS, now]. Es decir, el
    challenge debe haber sido emitido hace como máximo
    `auth_challenge_window_seconds` (default 60s) y no puede estar en el
    futuro respecto al reloj del servidor.

    Devuelve el valor int del challenge si es válido.
    Lanza AuthError si el formato es inválido o está fuera de ventana.
    """
    try:
        challenge_ts = int(challenge)
    except (TypeError, ValueError) as exc:
        raise AuthError("challenge inválido: no es un timestamp entero") from exc

    now = int(time.time())
    window = settings.auth_challenge_window_seconds

    if challenge_ts > now:
        raise AuthError("challenge inválido: timestamp en el futuro")
    if challenge_ts < now - window:
        raise AuthError(
            f"challenge expirado: debe estar dentro de los últimos {window} segundos"
        )

    return challenge_ts


def verify_challenge_signature(public_key_hex: str, challenge: str, signature_hex: str) -> None:
    """Verifica la ventana de tiempo Y la firma Ed25519 del challenge.

    Lanza AuthError si cualquiera de las dos validaciones falla.
    """
    validate_challenge_window(challenge)

    try:
        valid = verify_signature(public_key_hex, challenge, signature_hex)
    except CryptoError as exc:
        raise AuthError(str(exc)) from exc

    if not valid:
        raise AuthError("firma inválida — no corresponde a la public_key indicada")


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def create_access_token(*, user_id: int, legajo: str, role: str, public_key: str) -> str:
    """Crea un JWT con los datos mínimos necesarios para identificar al usuario
    en requests subsecuentes, sin tener que volver a la DB en cada request
    si no es necesario.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "legajo": legajo,
        "role": role,
        "public_key": public_key,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decodifica y valida un JWT. Lanza jwt.PyJWTError si es inválido/expirado."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Dependency de FastAPI: resuelve el User autenticado a partir del JWT.

    Importa el modelo dentro de la función para evitar un import circular
    entre security.py y models.py (models.py no depende de security.py,
    pero por las dudas se mantiene el import local aquí también).

    Carga `role` explícitamente con `selectinload` — es una relationship
    lazy-loaded de SQLAlchemy async, y acceder a `user.role.name` de forma
    síncrona en cualquier dependency downstream (ej. get_current_admin)
    dispara una query diferida fuera de contexto async válido
    (sqlalchemy.exc.MissingGreenlet). Cargarla acá, una sola vez, evita
    ese problema en todos los callers.
    """
    from models.models import User
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except Exception as exc:
        raise credentials_exception from exc

    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return user


async def get_current_admin(current_user=Depends(get_current_user)):
    """Dependency: exige que el usuario autenticado tenga rol admin.

    `current_user.role` ya viene cargado (selectinload) desde
    `get_current_user` — seguro de acceder de forma síncrona acá.
    """
    if current_user.role is None or current_user.role.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador",
        )
    return current_user