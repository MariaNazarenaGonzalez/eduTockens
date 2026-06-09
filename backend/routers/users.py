# DEO GLORIA

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from core.database import get_db
from core.security import get_current_user
from models.models import User, Role

router = APIRouter()


class UserResponse(BaseModel):
    legajo: str
    name: str
    email: str
    role: str


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return full profile of the authenticated user.
    Legajo is read from the JWT payload; full data is fetched from the DB.
    """
    legajo = current_user.get("legajo")
    if not legajo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: legajo ausente.",
        )

    result = await db.execute(select(User).where(User.legajo == legajo))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalar_one_or_none()
    role_name = role.name if role else "student"

    return UserResponse(
        legajo=user.legajo,
        name=user.name,
        email=user.email,
        role=role_name,
    )