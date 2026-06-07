# TODO: Implement endpoints to list products, return product details, and serve product images.

from fastapi import APIRouter, Depends
from core.security import get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price_points: int
    stock: Optional[int]
    active: bool

@router.get("/", response_model=list[ProductResponse])
async def get_products(current_user: dict = Depends(get_current_user)):
    """
    List all active products
    """
    # TODO: Query products from database
    return [
        ProductResponse(
            id=1,
            name="Café",
            description="Taza de café del campus",
            price_points=50,
            stock=100,
            active=True
        ),
        ProductResponse(
            id=2,
            name="Empanada",
            description="Empanada de carne",
            price_points=40,
            stock=50,
            active=True
        )
    ]

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, current_user: dict = Depends(get_current_user)):
    """
    Get product details
    """
    # TODO: Query specific product from database
    return ProductResponse(
        id=product_id,
        name="Producto",
        description="Descripción del producto",
        price_points=50,
        stock=100,
        active=True
    )

@router.get("/{product_id}/image")
async def get_product_image(product_id: int, current_user: dict = Depends(get_current_user)):
    """
    Serve product image
    """
    # TODO: Return product image from database
    return {"message": "Image not available"}