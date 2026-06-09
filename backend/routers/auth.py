from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from core.database import get_db
from core.security import hash_password, verify_password, create_access_token
from models.models import User, Role

router = APIRouter()


class RegisterRequest(BaseModel):
    legajo: str
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    identifier: str  # Accepts legajo or email
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new student. Legajo and email must be unique.
    """
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
        password_hash=hash_password(data.password),
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
    Authenticate user by legajo or email + password. Returns JWT with sub (email),
    legajo, and role embedded in the payload.
    """
    result = await db.execute(
        select(User).where(
            or_(User.legajo == data.identifier, User.email == data.identifier)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas.",
        )

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