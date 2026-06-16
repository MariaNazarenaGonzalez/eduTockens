from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from core.database import get_db
from core.security import create_access_token
from models.models import User, Role

router = APIRouter()


CHALLENGE_FORMAT = "%Y-%m-%d %H:%M"


class RegisterRequest(BaseModel):
    legajo: str
    name: str
    email: EmailStr
    public_key_pem: str
    challenge: str
    signature: str


class LoginRequest(BaseModel):
    identifier: str  # Accepts legajo or email
    challenge: str
    signature: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def current_challenge() -> str:
    return datetime.now().strftime(CHALLENGE_FORMAT)


def is_valid_challenge(challenge: str) -> bool:
    now = datetime.now()
    valid_challenges = {
        (now + timedelta(minutes=offset)).strftime(CHALLENGE_FORMAT)
        for offset in (-1, 0, 1)
    }
    return challenge in valid_challenges


def validate_public_key(public_key_pem: str):
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La clave pública debe estar en formato PEM.",
        )

    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La clave pública debe ser ECDSA.",
        )

    return public_key


def verify_signed_challenge(public_key_pem: str, challenge: str, signature_hex: str):
    if not is_valid_challenge(challenge):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El desafío expiró. Solicitá uno nuevo.",
        )

    try:
        signature = bytes.fromhex(signature_hex)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La firma debe estar codificada en hexadecimal.",
        )

    public_key = validate_public_key(public_key_pem)
    try:
        public_key.verify(
            signature,
            challenge.encode("utf-8"),
            ec.ECDSA(hashes.SHA1()),
        )
    except InvalidSignature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma inválida para el desafío provisto.",
        )


@router.get("/challenge")
async def get_challenge():
    """
    Return the current server challenge. It changes once per minute.
    """
    return {"challenge": current_challenge()}


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new student with a public key. Legajo and email must be unique.
    """
    verify_signed_challenge(data.public_key_pem, data.challenge, data.signature)

    # Check legajo not taken
    result = await db.execute(select(User).where(User.legajo == data.legajo))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El legajo ya está registrado.",
        )

    # Check email not taken
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado.",
        )

    # Resolve student role id
    result = await db.execute(select(Role).where(Role.name == "student"))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Rol 'student' no encontrado. Verificar inicialización de la base de datos.",
        )

    user = User(
        legajo=data.legajo,
        name=data.name,
        email=data.email,
        public_key_pem=data.public_key_pem,
        role_id=role.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {
        "message": "Registro exitoso.",
        "user": {
            "legajo": user.legajo,
            "name": user.name,
            "email": user.email,
        },
    }


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user by legajo or email + ECDSA signed challenge. Returns JWT
    with sub (email), legajo, and role embedded in the payload.
    """
    result = await db.execute(
        select(User).where(
            or_(User.legajo == data.identifier, User.email == data.identifier)
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas.",
        )

    verify_signed_challenge(user.public_key_pem, data.challenge, data.signature)

    # Resolve role name
    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalar_one_or_none()
    role_name = role.name if role else "student"

    token = create_access_token({
        "sub": user.email,
        "legajo": user.legajo,
        "role": role_name,
    })

    return TokenResponse(
        access_token=token,
        user={
            "legajo": user.legajo,
            "name": user.name,
            "email": user.email,
            "role": role_name,
        },
    )


@router.post("/logout")
async def logout():
    """
    Stateless logout. The client discards the JWT locally.
    Server-side invalidation is documented as a known limitation.
    """
    return {"message": "Logout exitoso."}
