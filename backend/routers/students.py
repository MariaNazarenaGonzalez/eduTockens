# DEO GLORIA

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.security import get_current_user
from models.models import User, Purchase

router = APIRouter()


class BalanceResponse(BaseModel):
    legajo: str
    balance: int


class TransactionItem(BaseModel):
    id: int
    product_id: int
    points_spent: int
    created_at: str


@router.get("/{legajo}/balance", response_model=BalanceResponse)
async def get_student_balance(
    legajo: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Devuelve el saldo del estudiante. Actualmente devuelve un placeholder
    hasta que se integre la lógica con NCT/blockchain.
    """
    # Security: students can only read their own balance, admins can read any
    requester_legajo = current_user.get("legajo")
    role = current_user.get("role")
    if role != "admin" and requester_legajo != legajo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    result = await db.execute(select(User).where(User.legajo == legajo))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    # TODO: integrar con NCT/blockchain para obtener saldo real.
    # Por ahora devolvemos 0 como placeholder para evitar 404 en frontend.
    return BalanceResponse(legajo=legajo, balance=0)


@router.get("/{legajo}/transactions", response_model=List[TransactionItem])
async def get_student_transactions(
    legajo: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Devuelve las transacciones (purchases) del estudiante.
    """
    requester_legajo = current_user.get("legajo")
    role = current_user.get("role")
    if role != "admin" and requester_legajo != legajo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    result = await db.execute(select(User).where(User.legajo == legajo))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    purchases_result = await db.execute(select(Purchase).where(Purchase.user_id == user.id).order_by(Purchase.id.desc()))
    purchases = purchases_result.scalars().all()

    return [
        TransactionItem(
            id=p.id,
            product_id=p.product_id,
            points_spent=p.points_spent,
            created_at=p.purchased_at.isoformat() if p.purchased_at else None,
        )
        for p in purchases
    ]
