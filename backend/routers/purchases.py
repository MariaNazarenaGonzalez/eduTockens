# DEO GLORIA

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.security import get_current_user
from core.database import get_db
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from models.models import Product, Purchase, User

router = APIRouter()

class PurchaseRequest(BaseModel):
    product_id: int

class PurchaseResponse(BaseModel):
    id: int
    product_id: int
    points_spent: int
    purchased_at: datetime
    nct_transaction_id: Optional[str]

    class Config:
        from_attributes = True

@router.post("/", response_model=dict)
async def create_purchase(
    data: PurchaseRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Process purchase and emit SPEND transaction
    """
    # --- Validate product ---
    result = await db.execute(
        select(Product).where(Product.id == data.product_id, Product.active == True)
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado o no disponible.",
        )

    # Check stock availability (stock == None means unlimited)
    if product.stock is not None and product.stock <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Producto sin stock disponible.",
        )

    # --- Validate user exists ---
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

    # TODO: Validate balance via NCT (get_balance) and verify user has enough points

    # TODO: Emit SPEND transaction to NCT

    # --- Record purchase in database ---
    purchase = Purchase(
        user_id=user.id,
        product_id=product.id,
        points_spent=product.price_points,
        nct_transaction_id=None,  # Will be set once NCT integration is complete
    )
    db.add(purchase)

    # Decrement stock if not unlimited
    if product.stock is not None:
        product.stock -= 1

    await db.commit()
    await db.refresh(purchase)

    return {
        "message": "Compra realizada exitosamente",
        "purchase_id": purchase.id,
        "transaction_id": purchase.nct_transaction_id,
        "points_spent": purchase.points_spent,
    }

@router.get("/me", response_model=list[PurchaseResponse])
async def get_my_purchases(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get purchase history of current user
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

    # Query purchases from database
    result = await db.execute(
        select(Purchase)
        .where(Purchase.user_id == user.id)
        .order_by(Purchase.purchased_at.desc())
    )
    purchases = result.scalars().all()
    return purchases