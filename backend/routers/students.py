# DEO GLORIA

"""Endpoints de consulta para estudiantes: balance (+ nonce) y transacciones."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.models import TransactionLog, User
from schemas.schemas import BalanceResponse, TransactionLogResponse
from services.nct_client import NCTError, nct_client

router = APIRouter(prefix="/students", tags=["students"])


async def _get_student_or_404(db: AsyncSession, legajo: str) -> User:
    result = await db.execute(select(User).where(User.legajo == legajo))
    student = result.scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=404, detail=f"No existe un estudiante con legajo {legajo}")
    return student


@router.get("/{legajo}/balance", response_model=BalanceResponse)
async def get_balance(legajo: str, db: AsyncSession = Depends(get_db)) -> BalanceResponse:
    """Balance confirmado + nonce actual (necesario para que el frontend
    pueda firmar la próxima transacción SPEND sin pegarle directamente al NCT).
    """
    student = await _get_student_or_404(db, legajo)

    try:
        account = await nct_client.get_account(student.public_key)
    except NCTError as exc:
        raise HTTPException(status_code=502, detail=f"Error consultando el NCT: {exc}") from exc

    return BalanceResponse(
        legajo=student.legajo,
        public_key=student.public_key,
        balance=account["balance"],
        nonce=account["nonce"],
    )


@router.get("/{legajo}/transactions", response_model=list[TransactionLogResponse])
async def get_transactions(legajo: str, db: AsyncSession = Depends(get_db)) -> list[TransactionLogResponse]:
    """Historial de transacciones del estudiante, leído de la tabla local
    `transactions_log` (poblada por el backend al emitir cada EARN/SPEND).
    No se consulta /chain del NCT en cada request — ver justificación en
    el modelo de datos (db/init.sql).
    """
    student = await _get_student_or_404(db, legajo)

    result = await db.execute(
        select(TransactionLog)
        .where(TransactionLog.user_id == student.id)
        .order_by(TransactionLog.created_at.desc())
    )
    logs = result.scalars().all()
    return [TransactionLogResponse.model_validate(log) for log in logs]