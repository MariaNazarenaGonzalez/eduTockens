# DEO GLORIA

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# Auth Schemas
class UserRegister(BaseModel):
    legajo: str
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: str
    password: str
    role: str = "student"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

# User Schemas
class UserResponse(BaseModel):
    id: int
    legajo: str
    name: str
    email: str
    role: str
    created_at: datetime

# Product Schemas
class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price_points: int
    stock: Optional[int] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_points: Optional[int] = None
    stock: Optional[int] = None

class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price_points: int
    stock: Optional[int]
    active: bool
    created_at: datetime

# Purchase Schemas
class PurchaseCreate(BaseModel):
    product_id: int

class PurchaseResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    points_spent: int
    purchased_at: datetime
    nct_transaction_id: Optional[str]

# Admin Schemas
class EarnRequest(BaseModel):
    legajo: str
    amount: int
    concept: str

class AdminStats(BaseModel):
    students: int
    transactions: int
    blocks: int
    total_supply: int