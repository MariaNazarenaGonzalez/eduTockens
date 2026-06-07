# TODO: Implement user endpoints, including the authenticated current user profile.

from fastapi import APIRouter, Depends
from core.security import get_current_user
from pydantic import BaseModel

router = APIRouter()

class UserResponse(BaseModel):
    legajo: str
    name: str
    email: str
    role: str

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user profile
    """
    # TODO: Fetch full user data from database
    return UserResponse(
        legajo="12345678",
        name="Nombre del Estudiante",
        email=current_user.get("sub", "user@example.com"),
        role=current_user.get("role", "student")
    )