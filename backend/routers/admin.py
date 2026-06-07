# TODO: Implement admin endpoints for issuing points (EARN) and managing marketplace products.

from fastapi import APIRouter, Depends, HTTPException
from core.security import get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class EarnRequest(BaseModel):
    legajo: str
    amount: int
    concept: str

class ProductCreateRequest(BaseModel):
    name: str
    description: Optional[str]
    price_points: int
    stock: Optional[int]

class StatsResponse(BaseModel):
    students: int
    transactions: int
    blocks: int
    total_supply: int

@router.post("/earn", response_model=dict)
async def emit_points(data: EarnRequest, current_user: dict = Depends(get_current_user)):
    """
    Emit points to student (admin only)
    """
    # TODO: Verify admin role
    # TODO: Emit EARN transaction to NCT
    return {
        "message": "Points emitted successfully",
        "transaction_id": "tx_earn_12345"
    }

@router.get("/stats", response_model=StatsResponse)
async def get_stats(current_user: dict = Depends(get_current_user)):
    """
    Get system statistics
    """
    # TODO: Query stats from database and NCT
    return StatsResponse(
        students=100,
        transactions=5000,
        blocks=150,
        total_supply=50000
    )

@router.get("/products")
async def get_all_products(current_user: dict = Depends(get_current_user)):
    """
    Get all products (active and inactive)
    """
    # TODO: Query all products from database
    return []

@router.post("/products", response_model=dict)
async def create_product(data: ProductCreateRequest, current_user: dict = Depends(get_current_user)):
    """
    Create new product
    """
    # TODO: Create product in database
    return {"message": "Product created", "id": 1}

@router.delete("/products/{product_id}", response_model=dict)
async def delete_product(product_id: int, current_user: dict = Depends(get_current_user)):
    """
    Delete product
    """
    # TODO: Mark product as inactive
    return {"message": "Product deleted"}