# DEO GLORIA

"""Modelos SQLAlchemy ORM para eduTockens.

Cambios respecto al diseño original (auth por password):
- `User.password_hash` → `User.public_key` (auth por challenge firmado Ed25519).
- Nueva entidad `Vendor`: solo guarda una pubkey receptora de SPEND. No es un
  usuario, no hace login, no firma nada. El backend genera su keypair al
  crearlo y descarta la privada inmediatamente.
- `Product.vendor_id`: a qué vendor pertenece el producto.
- Nueva entidad `TransactionLog`: índice local de EARN/SPEND por estudiante,
  poblado por el backend en el momento de emitir cada transacción al NCT.
  Sirve GET /students/{legajo}/transactions sin tener que leer /chain.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base):
    """Estudiante o administrador.

    Auth de DOS FACTORES:
    1. `public_key` (64 hex, Ed25519) — el usuario prueba posesión de la
       clave privada firmando un challenge.
    2. `password_hash` (bcrypt) — el mismo password que el usuario usa
       para cifrar su clave privada en localStorage del lado cliente.

    `public_key` es además la identidad criptográfica usada como
    `sender_pubkey`/`receiver_pubkey` en transacciones del NCT.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(r"public_key ~ '^[0-9a-f]{64}$'", name="chk_users_public_key_hex"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legajo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    public_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(60), nullable=False)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    role: Mapped["Role"] = relationship(back_populates="users")
    purchases: Mapped[list["Purchase"]] = relationship(back_populates="user")
    transactions: Mapped[list["TransactionLog"]] = relationship(back_populates="user")

    @property
    def nct_pubkey(self) -> str:
        """Alias semántico: la pubkey de este usuario tal como la espera el NCT."""
        return self.public_key


class Vendor(Base):
    """Proveedor del marketplace (fotocopiadora, máquina expendedora, etc.).

    Solo importa su `public_key`: es la dirección receptora de las
    transacciones SPEND. Es una "burn address" — nadie posee ni usa la
    clave privada correspondiente (se generó y se descartó al crear el
    vendor). No es un usuario: no hace login, no tiene rol, no firma nada.
    """

    __tablename__ = "vendors"
    __table_args__ = (
        CheckConstraint(r"public_key ~ '^[0-9a-f]{64}$'", name="chk_vendors_public_key_hex"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    public_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    products: Mapped[list["Product"]] = relationship(back_populates="vendor")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price_points: Mapped[int] = mapped_column(Integer, nullable=False)
    stock: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    image_data: Mapped[bytes | None] = mapped_column(LargeBinary)
    image_mime_type: Mapped[str | None] = mapped_column(String(50))
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    vendor: Mapped["Vendor"] = relationship(back_populates="products")
    purchases: Mapped[list["Purchase"]] = relationship(back_populates="product")


class Purchase(Base):
    """Registro de una compra. `nct_transaction_id` cruza con el SPEND minado en el NCT."""

    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    points_spent: Mapped[int] = mapped_column(Integer, nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    nct_transaction_id: Mapped[str | None] = mapped_column(String(100))

    user: Mapped["User"] = relationship(back_populates="purchases")
    product: Mapped["Product"] = relationship(back_populates="purchases")


class TransactionLog(Base):
    """Índice local (caché de lectura) de EARN/SPEND por estudiante.

    Poblado por el backend en el mismo momento en que emite una transacción
    al NCT (tanto si la emite él mismo —EARN— como si solo reenvía una ya
    firmada por el cliente —SPEND—). El NCT sigue siendo la fuente de verdad;
    esta tabla solo evita tener que leer /chain en cada GET de historial.
    """

    __tablename__ = "transactions_log"
    __table_args__ = (
        CheckConstraint("tx_type IN ('EARN', 'SPEND')", name="chk_transactions_log_tx_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    tx_type: Mapped[str] = mapped_column(String(10), nullable=False)
    counterparty_pubkey: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    concept: Mapped[str] = mapped_column(String(128), nullable=False)
    nct_tx_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="transactions")