# DEO GLORIA

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from pydantic import BaseModel

from core.security import get_current_user
from core.database import get_db
from models.models import User, Product, Role

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency: verificar rol admin
# ---------------------------------------------------------------------------

async def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol admin")
    return current_user


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class EarnRequest(BaseModel):
    legajo: str
    amount: int
    concept: str

class StatsResponse(BaseModel):
    students: int
    transactions: int
    blocks: int
    total_supply: int

class StockUpdate(BaseModel):
    stock: Optional[int] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/earn", response_model=dict)
async def emit_points(
    data: EarnRequest,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Emit points to a student (admin only).
    Verifies that the student exists in the database before forwarding to NCT.
    """
    result = await db.execute(select(User).where(User.legajo == data.legajo))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail=f"Estudiante con legajo '{data.legajo}' no encontrado")

    # TODO: Emit EARN transaction to NCT
    return {
        "message": "Puntos emitidos exitosamente",
        "transaction_id": "tx_earn_pending"
    }


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get system statistics.
    Student count is queried from the database; blockchain stats delegate to NCT (pending).
    """
    # Count students by joining with the "student" role
    role_result = await db.execute(select(Role).where(Role.name == "student"))
    student_role = role_result.scalar_one_or_none()

    student_count = 0
    if student_role:
        count_result = await db.execute(
            select(func.count(User.id)).where(User.role_id == student_role.id)
        )
        student_count = count_result.scalar() or 0

    # TODO: Query transactions, blocks and total_supply from NCT
    return StatsResponse(
        students=student_count,
        transactions=0,
        blocks=0,
        total_supply=0
    )


@router.get("/products")
async def get_all_products(
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    List all products, both active and inactive.
    Image binary is excluded from this listing; use GET /products/{id}/image to retrieve it.
    """
    result = await db.execute(select(Product))
    products = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "price_points": p.price_points,
            "stock": p.stock,
            "active": p.active,
            "has_image": p.image_data is not None,
            "image_mime_type": p.image_mime_type,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in products
    ]


@router.post("/products", response_model=dict)
async def create_product(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    price_points: int = Form(...),
    stock: Optional[int] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new product. Accepts multipart/form-data; image is optional.
    stock = NULL means unlimited stock.
    """
    image_data = None
    image_mime_type = None
    if image:
        image_data = await image.read()
        image_mime_type = image.content_type

    product = Product(
        name=name,
        description=description,
        price_points=price_points,
        stock=stock,
        image_data=image_data,
        image_mime_type=image_mime_type,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return {"message": "Producto creado", "id": product.id}


@router.put("/products/{product_id}", response_model=dict)
async def update_product(
    product_id: int,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    price_points: int = Form(...),
    stock: Optional[int] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing product. Image is optional; if not provided, the existing image is kept.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    product.name = name
    product.description = description
    product.price_points = price_points
    product.stock = stock
    if image:
        product.image_data = await image.read()
        product.image_mime_type = image.content_type

    await db.commit()
    return {"message": "Producto actualizado"}


@router.patch("/products/{product_id}/stock", response_model=dict)
async def update_stock(
    product_id: int,
    data: StockUpdate,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update only the stock of a product. stock = null means unlimited.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    product.stock = data.stock
    await db.commit()
    return {"message": "Stock actualizado"}


@router.delete("/products/{product_id}", response_model=dict)
async def delete_product(
    product_id: int,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Soft-delete a product: marks it as inactive (active = FALSE).
    The record is preserved to maintain referential integrity with purchases.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    product.active = False
    await db.commit()
    return {"message": "Producto dado de baja"}