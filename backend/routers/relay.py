# DEO GLORIA

"""POST /transactions/relay — relay de SPEND firmadas por el estudiante.

Recibe una transacción SPEND YA FIRMADA desde la wallet del estudiante,
la reenvía al NCT, y registra el resultado en TransactionLog.

EARN NO pasa por este endpoint — va por POST /admin/earn donde el
backend firma con la clave institucional.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user  # autenticación JWT requerida
from models.models import TransactionLog, User
from schemas.schemas import RelayRequest, RelayResponse
from services.nct_client import NCTError, nct_client

router = APIRouter(prefix="/transactions", tags=["transactions"])


async def _resolve_user_by_pubkey(db: AsyncSession, pubkey: str) -> User | None:
    """Busca un User por su public_key. Retorna None si no hay match."""
    result = await db.execute(select(User).where(User.public_key == pubkey))
    return result.scalar_one_or_none()


@router.post("/relay", response_model=RelayResponse, status_code=201)
async def relay_transaction(
    body: RelayRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RelayResponse:
    """Reenvía una transacción firmada al NCT y la registra localmente.

    La wallet del frontend ya construyó el signing dict, calculó tx_id
    y firmó. Este endpoint solo:

    1. Reenvía el payload textual al NCT vía POST /transaction.
    2. Si el NCT acepta (201), registra en TransactionLog.
    3. Si el NCT rechaza (400), propaga el error.

    No distingue entre EARN y SPEND — el NCT valida la autorización
    (EARN solo desde AUTHORITY_PUBKEY) y la firma.
    """
    # 1. Reenviar al NCT
    try:
        nct_result = await nct_client.relay_transaction(body.model_dump())
    except NCTError as exc:
        raise HTTPException(
            status_code=502 if exc.status_code is None else 400,
            detail=f"NCT rechazó la transacción: {exc}",
        ) from exc

    tx_id = nct_result["tx_id"]

    # 2. El relay solo maneja SPEND (EARN va por POST /admin/earn).
    #    El estudiante que firma es el sender.
    student = await _resolve_user_by_pubkey(db, body.sender_pubkey)

    # 3. Registrar en TransactionLog (solo si la pubkey matchea un User)
    if student is not None:
        db.add(
            TransactionLog(
                user_id=student.id,
                tx_type="SPEND",
                counterparty_pubkey=body.receiver_pubkey,
                amount=int(body.amount),
                concept=body.concept,
                nct_tx_id=tx_id,
                # triggered_by_admin_id queda NULL (SPEND no tiene admin)
            )
        )
        await db.commit()

    return RelayResponse(tx_id=tx_id)
