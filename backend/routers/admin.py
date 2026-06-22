# DEO GLORIA

"""Endpoints de administración: emisión de puntos (EARN vía relay),
resolución legajo→pubkey, gestión de vendors y productos,
estadísticas globales.  El backend NO firma EARN — lo hace la
wallet del admin en el navegador.

Todos requieren rol admin (Depends(get_current_admin)).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.crypto import generate_keypair_hex
from core.database import get_db
from core.security import get_current_admin
from models.models import Product, Purchase, TransactionLog, User, Vendor
from schemas.schemas import (
    AdminStats,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    PurchaseLogResponse,
    VendorCreate,
    VendorResponse,
)
from services.nct_client import NCTError, nct_client

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


# ---------------------------------------------------------------------------
# Resolve — traduce legajo → pubkey para la wallet del admin
# ---------------------------------------------------------------------------


class ResolveResponse(BaseModel):
    public_key: str
    student_name: str


@router.get("/resolve", response_model=ResolveResponse)
async def resolve_legajo(legajo: str, db: AsyncSession = Depends(get_db)) -> ResolveResponse:
    """Traduce un legajo a su clave pública.  Lo usa la wallet del admin
    para saber a qué pubkey emitir un EARN.
    """
    result = await db.execute(select(User).where(User.legajo == legajo))
    student = result.scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=404, detail=f"No existe un estudiante con legajo {legajo}")

    return ResolveResponse(public_key=student.public_key, student_name=student.name)


# ---------------------------------------------------------------------------
# Account — nonce de la autoridad para que la wallet del admin pueda firmar
# ---------------------------------------------------------------------------


@router.get("/account")
async def admin_account() -> dict:
    """Devuelve la cuenta NCT de la autoridad académica (balance + pending_nonce).
    La wallet del admin necesita el nonce antes de firmar un EARN.
    """
    from core.config import settings

    try:
        return await nct_client.get_account(settings.authority_public_key)
    except NCTError as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo consultar el NCT: {exc}")


# ---------------------------------------------------------------------------
# Vendors
# ---------------------------------------------------------------------------


@router.post("/vendors", response_model=VendorResponse, status_code=201)
async def create_vendor(body: VendorCreate, db: AsyncSession = Depends(get_db)) -> VendorResponse:
    """Crea un vendor nuevo. El backend genera un keypair Ed25519 y
    descarta la clave privada inmediatamente — solo se persiste la pubkey.
    El vendor nunca firma nada (no es una cuenta operable, es una
    dirección receptora pasiva de SPEND).
    """
    _private_key_discarded, public_key = generate_keypair_hex()
    # La línea anterior es intencional: la privkey no se asigna a ninguna
    # variable de uso posterior ni se persiste en ningún lado. Existe solo
    # en este scope y se pierde al retornar.

    vendor = Vendor(name=body.name, public_key=public_key)
    db.add(vendor)
    await db.commit()
    await db.refresh(vendor)

    return VendorResponse.model_validate(vendor)


@router.get("/vendors", response_model=list[VendorResponse])
async def list_vendors(db: AsyncSession = Depends(get_db)) -> list[VendorResponse]:
    result = await db.execute(select(Vendor).order_by(Vendor.id))
    vendors = result.scalars().all()
    return [VendorResponse.model_validate(v) for v in vendors]


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


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


@router.get("/products", response_model=list[ProductResponse])
async def admin_list_products(db: AsyncSession = Depends(get_db)) -> list[ProductResponse]:
    result = await db.execute(select(Product).order_by(Product.id))
    products = result.scalars().all()
    return [await _product_to_response(db, p) for p in products]


@router.post("/products", response_model=ProductResponse, status_code=201)
async def create_product(body: ProductCreate, db: AsyncSession = Depends(get_db)) -> ProductResponse:
    vendor_result = await db.execute(select(Vendor).where(Vendor.id == body.vendor_id))
    if vendor_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"No existe vendor con id {body.vendor_id}")

    product = Product(
        name=body.name,
        description=body.description,
        price_points=body.price_points,
        stock=body.stock,
        vendor_id=body.vendor_id,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)

    return await _product_to_response(db, product)


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int, body: ProductUpdate, db: AsyncSession = Depends(get_db)
) -> ProductResponse:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    if body.vendor_id is not None:
        vendor_result = await db.execute(select(Vendor).where(Vendor.id == body.vendor_id))
        if vendor_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail=f"No existe vendor con id {body.vendor_id}")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)

    return await _product_to_response(db, product)


@router.delete("/products/{product_id}", status_code=204, response_model=None)
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    await db.delete(product)
    await db.commit()


# ---------------------------------------------------------------------------
# Purchases (logs) — todas las compras, no solo las del usuario actual
# ---------------------------------------------------------------------------


@router.get("/purchases", response_model=list[PurchaseLogResponse])
async def list_all_purchases(db: AsyncSession = Depends(get_db)) -> list[PurchaseLogResponse]:
    """Últimas 30 compras de TODOS los estudiantes, con datos del usuario y
    producto — alimenta el tab "Logs" del panel admin. Lee directamente de
    la base de datos local de eduTockens (tabla `purchases`), no del NCT.
    """
    result = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.user), selectinload(Purchase.product))
        .order_by(Purchase.purchased_at.desc())
        .limit(30)
    )
    purchases = result.scalars().all()

    return [
        PurchaseLogResponse(
            id=p.id,
            legajo=p.user.legajo if p.user else "?",
            product_name=p.product.name if p.product else "?",
            points_spent=p.points_spent,
            purchased_at=p.purchased_at,
            nct_transaction_id=p.nct_transaction_id,
        )
        for p in purchases
    ]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=AdminStats)
async def get_stats(db: AsyncSession = Depends(get_db)) -> AdminStats:
    from models.models import Role

    student_role_subq = select(Role.id).where(Role.name == "student").scalar_subquery()

    total_students = (
        await db.execute(select(func.count()).select_from(User).where(User.role_id == student_role_subq))
    ).scalar_one()
    total_vendors = (await db.execute(select(func.count()).select_from(Vendor))).scalar_one()
    total_products = (await db.execute(select(func.count()).select_from(Product))).scalar_one()
    total_purchases = (await db.execute(select(func.count()).select_from(Purchase))).scalar_one()
    total_points_spent = (
        await db.execute(select(func.coalesce(func.sum(Purchase.points_spent), 0)))
    ).scalar_one()

    return AdminStats(
        total_students=total_students,
        total_vendors=total_vendors,
        total_products=total_products,
        total_purchases=total_purchases,
        total_points_spent=int(total_points_spent),
    )