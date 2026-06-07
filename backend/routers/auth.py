# TODO: Implement authentication endpoints for user registration, login, and logout.

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from core.security import hash_password, verify_password, create_access_token

router = APIRouter()

class RegisterRequest(BaseModel):
    legajo: str
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str
    role: str = "student"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

@router.post("/register", response_model=dict)
async def register(data: RegisterRequest):
    """
    Register a new student
    """
    # TODO: Implement user creation in database
    return {
        "message": "Registration successful",
        "user": {
            "legajo": data.legajo,
            "name": data.name,
            "email": data.email
        }
    }

@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest):
    """
    Login user and return JWT token
    """
    # TODO: Implement user verification against database
    # Placeholder response
    token = create_access_token({
        "sub": data.email,
        "role": data.role
    })
    
    return TokenResponse(
        access_token=token,
        user={
            "email": data.email,
            "role": data.role,
            "legajo": "12345678"
        }
    )

@router.post("/logout")
async def logout():
    """
    Logout user (stateless - just confirm)
    """
    return {"message": "Logout successful"}