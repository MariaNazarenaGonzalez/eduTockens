# DEO GLORIA

"""Endpoints de autenticación — challenge firmado con Ed25519 (sin password)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import (
    AuthError,
    create_access_token,
    generate_challenge,
    hash_password,
    verify_challenge_signature,
    verify_password,
)
from models.models import Role, User
from schemas.schemas import (
    ChallengeResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/challenge", response_model=ChallengeResponse)
async def get_challenge() -> ChallengeResponse:
    """Devuelve el timestamp actual del servidor (segundos, entero) como
    string. No se persiste en ningún lado — la validez se controla
    recalculando la ventana de tiempo en el momento de /login o /register.
    """
    return ChallengeResponse(challenge=generate_challenge())


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> UserPublic:
    # La firma se verifica con la public_key que viene en el body — el
    # usuario todavía no existe en la DB, así que no hay otra fuente.
    try:
        verify_challenge_signature(body.public_key, body.challenge, body.signature)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Unicidad
    existing = await db.execute(
        select(User).where(
            (User.legajo == body.legajo)
            | (User.email == body.email)
            | (User.public_key == body.public_key)
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="Ya existe un usuario con ese legajo, email o public_key",
        )

    role_result = await db.execute(select(Role).where(Role.name == "student"))
    student_role = role_result.scalar_one_or_none()
    if student_role is None:
        raise HTTPException(
            status_code=500,
            detail="Rol 'student' no configurado — revisar seed de roles",
        )

    user = User(
        legajo=body.legajo,
        name=body.name,
        email=body.email,
        public_key=body.public_key,
        password_hash=hash_password(body.password),
        role_id=student_role.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user, attribute_names=["role"])

    return UserPublic(
        id=user.id,
        legajo=user.legajo,
        name=user.name,
        email=user.email,
        public_key=user.public_key,
        role=user.role.name,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    # Buscar al usuario por legajo o email para obtener su public_key y password_hash
    result = await db.execute(
        select(User).where(
            (User.legajo == body.identifier) | (User.email == body.identifier)
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        # No revelar si el identifier existe o no — mensaje genérico
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    # Factor 1: password (bcrypt) — "algo que sabés"
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    # Factor 2: firma Ed25519 del challenge — "algo que tenés" (la clave privada)
    try:
        verify_challenge_signature(user.public_key, body.challenge, body.signature)
    except AuthError:
        raise HTTPException(status_code=401, detail="Credenciales inválidas") from None

    await db.refresh(user, attribute_names=["role"])
    role_name = user.role.name if user.role else "student"

    token = create_access_token(
        user_id=user.id, legajo=user.legajo, role=role_name, public_key=user.public_key
    )

    return TokenResponse(
        access_token=token,
        user=UserPublic(
            id=user.id,
            legajo=user.legajo,
            name=user.name,
            email=user.email,
            public_key=user.public_key,
            role=role_name,
        ),
    )


@router.post("/logout")
async def logout() -> dict:
    """JWT stateless: no hay invalidación del lado del servidor.
    El cliente simplemente descarta el token (ver limitaciones conocidas
    en el README de eduTockens).
    """
    return {"status": "ok"}