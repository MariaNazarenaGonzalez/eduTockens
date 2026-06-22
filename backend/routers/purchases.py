# DEO GLORIA

"""POST /purchases — reenvío de una transacción SPEND ya firmada por el
estudiante (su clave privada nunca llega al backend).

Contrato con el frontend:
    1. El frontend obtiene el producto vía GET /products/{id}, que incluye
       `price_points` y `vendor_pubkey`.
    2. El frontend obtiene su `nonce` actual vía GET /students/{legajo}/balance.
    3. El frontend arma el signing dict EXACTAMENTE como lo hace el NCT
       (sender_pubkey=su pubkey, receiver_pubkey=vendor_pubkey del producto,
       amount=price_points, tx_type="SPEND", concept=<nombre o id del
       producto>, timestamp=ahora, nonce=el consultado), calcula tx_id,
       firma con su clave privada (nunca sale del navegador).
    4. POST /purchases con {product_id, nonce, timestamp, signature}.
       amount y receiver_pubkey NO se mandan — el backend los reconstruye
       desde el producto en DB, para que el estudiante no pueda alterar
       el precio. Si el frontend firmó con valores distintos a los que
       el backend reconstruye, el NCT rechazará la firma (no calza el tx_id).

Comportamiento "best effort" (confirmado): un 201 del NCT se considera
éxito de la compra. No se espera a que la transacción sea minada — el
README del NCT documenta que la validación final de saldo ocurre al
armar el bloque, así que, en el peor caso, la transacción podría ser
descartada más tarde por saldo insuficiente (doble gasto). Esto queda
documentado como limitación conocida, igual que en la propuesta original.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from models.models import Product, Purchase, TransactionLog, User, Vendor
from schemas.schemas import PurchaseCreate, PurchaseResponse
from services.nct_client import NCTError, nct_client

router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.post("", response_model=PurchaseResponse, status_code=201)
async def create_purchase(
    body: PurchaseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PurchaseResponse:
    product_result = await db.execute(select(Product).where(Product.id == body.product_id))
    product = product_result.scalar_one_or_none()
    if product is None or not product.active:
        raise HTTPException(status_code=404, detail="Producto no encontrado o inactivo")

    if product.vendor_id is None:
        raise HTTPException(status_code=400, detail="El producto no tiene un vendor asignado")

    vendor_result = await db.execute(select(Vendor).where(Vendor.id == product.vendor_id))
    vendor = vendor_result.scalar_one_or_none()
    if vendor is None:
        raise HTTPException(status_code=400, detail="Vendor del producto no encontrado")

    if product.stock is not None and product.stock <= 0:
        raise HTTPException(status_code=400, detail="Producto sin stock")

    # El amount y receiver_pubkey los determina el SERVIDOR a partir del
    # producto en DB — el cliente no los manda. Si el frontend firmó con
    # otros valores, el tx_id no va a coincidir y el NCT rechazará la firma.
    try:
        nct_result = await nct_client.relay_transaction({
            "sender_pubkey": current_user.public_key,
            "receiver_pubkey": vendor.public_key,
            "amount": int(product.price_points),
            "tx_type": "SPEND",
            "concept": product.name,
            "nonce": body.nonce,
            "timestamp": body.timestamp,
            "signature": body.signature,
        })
    except NCTError as exc:
        # 400 del NCT (firma inválida, nonce desincronizado, saldo
        # insuficiente al momento del bloque, etc.) → se traduce a 400
        # propio para que el frontend pueda mostrar el motivo.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tx_id = nct_result["tx_id"]

    purchase = Purchase(
        user_id=current_user.id,
        product_id=product.id,
        points_spent=product.price_points,
        nct_transaction_id=tx_id,
    )
    db.add(purchase)

    db.add(
        TransactionLog(
            user_id=current_user.id,
            tx_type="SPEND",
            counterparty_pubkey=vendor.public_key,
            amount=product.price_points,
            concept=product.name,
            nct_tx_id=tx_id,
        )
    )

    if product.stock is not None:
        product.stock -= 1

    await db.commit()
    await db.refresh(purchase)

    return PurchaseResponse.model_validate(purchase)


@router.get("/me", response_model=list[PurchaseResponse])
async def my_purchases(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PurchaseResponse]:
    result = await db.execute(
        select(Purchase)
        .where(Purchase.user_id == current_user.id)
        .order_by(Purchase.purchased_at.desc())
    )
    purchases = result.scalars().all()
    return [PurchaseResponse.model_validate(p) for p in purchases]