# DEO GLORIA

"""Endpoint de perfil del usuario autenticado."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.security import get_current_user
from models.models import User
from schemas.schemas import UserPublic

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
async def get_me(current_user: User = Depends(get_current_user)) -> UserPublic:
    role_name = current_user.role.name if current_user.role else "student"
    return UserPublic(
        id=current_user.id,
        legajo=current_user.legajo,
        name=current_user.name,
        email=current_user.email,
        public_key=current_user.public_key,
        role=role_name,
    )