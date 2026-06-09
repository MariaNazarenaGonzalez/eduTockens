# DEO GLORIA

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from core.database import get_db
from core.security import get_current_user
from models.models import Product

router = APIRouter()


class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price_points: int
    stock: Optional[int]
    active: bool

    class Config:
        from_attributes = True


@router.get("/", response_model=list[ProductResponse])
async def get_products(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all active products available in the marketplace.
    """
    result = await db.execute(
        select(Product).where(Product.active == True).order_by(Product.id)
    )
    products = result.scalars().all()
    return products


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return details of a single active product.
    """
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.active == True)
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado.",
        )

    return product


@router.get("/{product_id}/image")
async def get_product_image(
    product_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Serve the binary image of a product with its original MIME type.
    Returns 404 if the product doesn't exist or has no image loaded.
    """
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.active == True)
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado.",
        )

    if not product.image_data or not product.image_mime_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El producto no tiene imagen cargada.",
        )

    return Response(
        content=product.image_data,
        media_type=product.image_mime_type,
    )