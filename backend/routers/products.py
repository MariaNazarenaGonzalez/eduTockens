# DEO GLORIA

"""Endpoints públicos de productos (marketplace) — solo lectura."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.models import Product
from schemas.schemas import ProductResponse

router = APIRouter(prefix="/products", tags=["products"])


async def _product_to_response(db: AsyncSession, product: Product) -> ProductResponse:
    vendor_pubkey = None
    if product.vendor_id is not None:
        await db.refresh(product, attribute_names=["vendor"])
        vendor_pubkey = product.vendor.public_key if product.vendor else None

    return ProductResponse(
        id=product.id,
        name=product.name,
        description=product.description,
        price_points=product.price_points,
        stock=product.stock,
        active=product.active,
        vendor_id=product.vendor_id,
        vendor_pubkey=vendor_pubkey,
        created_at=product.created_at,
    )


@router.get("", response_model=list[ProductResponse])
async def list_products(db: AsyncSession = Depends(get_db)) -> list[ProductResponse]:
    """Solo productos activos — esto alimenta el marketplace del estudiante."""
    result = await db.execute(select(Product).where(Product.active.is_(True)).order_by(Product.id))
    products = result.scalars().all()
    return [await _product_to_response(db, p) for p in products]


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)) -> ProductResponse:
    """Incluye `vendor_pubkey` — el frontend lo necesita como receiver_pubkey
    para armar y firmar la transacción SPEND ANTES de llamar a POST /purchases.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    return await _product_to_response(db, product)


@router.get("/{product_id}/image")
async def get_product_image(product_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None or product.image_data is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    return Response(content=product.image_data, media_type=product.image_mime_type or "image/png")