# DEO GLORIA

"""Esquemas Pydantic para requests/responses de eduTockens."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Auth — challenge firmado con Ed25519
# ---------------------------------------------------------------------------


class ChallengeResponse(BaseModel):
    challenge: str  # timestamp del servidor (segundos, entero, como string)


class RegisterRequest(BaseModel):
    legajo: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=150)
    public_key: str = Field(description="64 hex chars, clave pública Ed25519")
    password: str = Field(
        min_length=8,
        max_length=128,
        description=(
            "Segundo factor de autenticación (bcrypt). Es el MISMO password "
            "que el cliente usa para cifrar su clave privada en localStorage."
        ),
    )
    challenge: str
    signature: str = Field(description="128 hex chars — firma Ed25519 del challenge")

    @field_validator("public_key")
    @classmethod
    def _validate_pubkey(cls, v: str) -> str:
        from core.crypto import is_valid_pubkey_hex

        if not is_valid_pubkey_hex(v):
            raise ValueError("public_key debe ser 64 caracteres hex lowercase")
        return v

    @field_validator("signature")
    @classmethod
    def _validate_signature(cls, v: str) -> str:
        from core.crypto import is_valid_signature_hex

        if not is_valid_signature_hex(v):
            raise ValueError("signature debe ser 128 caracteres hex lowercase")
        return v


class LoginRequest(BaseModel):
    identifier: str = Field(description="legajo o email del usuario")
    password: str = Field(min_length=1, max_length=128)
    challenge: str
    signature: str = Field(description="128 hex chars — firma Ed25519 del challenge")


class UserPublic(BaseModel):
    id: int
    legajo: str
    name: str
    email: str
    public_key: str
    role: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


# ---------------------------------------------------------------------------
# Vendors
# ---------------------------------------------------------------------------


class VendorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class VendorResponse(BaseModel):
    id: int
    name: str
    public_key: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    price_points: int = Field(gt=0)
    stock: Optional[int] = Field(default=None, ge=0)
    vendor_id: int


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    price_points: Optional[int] = Field(default=None, gt=0)
    stock: Optional[int] = Field(default=None, ge=0)
    active: Optional[bool] = None
    vendor_id: Optional[int] = None


class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price_points: int
    stock: Optional[int]
    active: bool
    vendor_id: Optional[int]
    vendor_pubkey: Optional[str] = Field(
        default=None,
        description=(
            "Clave pública del vendor (64 hex chars). El frontend la usa "
            "directamente como receiver_pubkey al firmar el SPEND — no "
            "necesita consultar /vendors por separado."
        ),
    )
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Purchases (SPEND) — la transacción viene FIRMADA por el cliente.
# El backend NUNCA firma en nombre del estudiante.
# ---------------------------------------------------------------------------


class PurchaseCreate(BaseModel):
    """Payload de una compra. La transacción SPEND ya viene firmada por el
    navegador del estudiante (su clave privada nunca sale del cliente).
    El backend solo valida estructura, calcula montos, reenvía al NCT y
    persiste el resultado.
    """

    product_id: int
    nonce: int = Field(ge=0)
    timestamp: float
    signature: str = Field(description="128 hex chars — firma Ed25519 del tx_id")

    @field_validator("signature")
    @classmethod
    def _validate_signature(cls, v: str) -> str:
        from core.crypto import is_valid_signature_hex

        if not is_valid_signature_hex(v):
            raise ValueError("signature debe ser 128 caracteres hex lowercase")
        return v


class PurchaseResponse(BaseModel):
    id: int
    product_id: int
    points_spent: int
    purchased_at: datetime
    nct_transaction_id: Optional[str]

    model_config = {"from_attributes": True}


class PurchaseLogResponse(BaseModel):
    """Vista de una compra para el panel admin — incluye legajo y nombre
    de producto (denormalizado), a diferencia de PurchaseResponse que es
    para el propio estudiante (que ya sabe quién es)."""

    id: int
    legajo: str
    product_name: str
    points_spent: int
    purchased_at: datetime
    nct_transaction_id: Optional[str]


# ---------------------------------------------------------------------------
# Earn — el backend firma con la clave institucional.
# El admin solo manda legajo + amount + concept; el backend resuelve
# la pubkey y firma con AUTHORITY_PRIVATE_KEY.
# ---------------------------------------------------------------------------


class EarnRequest(BaseModel):
    legajo: str = Field(min_length=1, max_length=20)
    amount: int = Field(gt=0, le=1_000_000_000)
    concept: str = Field(min_length=1, max_length=128)


class EarnResponse(BaseModel):
    tx_id: str
    legajo: str
    amount: int
    concept: str


# ---------------------------------------------------------------------------
# Transactions log (historial)
# ---------------------------------------------------------------------------


class TransactionLogResponse(BaseModel):
    id: int
    tx_type: str
    counterparty_pubkey: str
    amount: int
    concept: str
    nct_tx_id: Optional[str]
    triggered_by_admin_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class BalanceResponse(BaseModel):
    legajo: str
    public_key: str
    balance: int
    nonce: int = Field(description="Nonce confirmado on-chain (solo para debug/UI)")
    pending_nonce: int = Field(
        description=(
            "Nonce que DEBE usarse en la próxima transacción. Considera las txs "
            "ya enviadas al pool. Regla de oro: siempre usar pending_nonce, "
            "nunca nonce, al construir una tx nueva."
        )
    )


# ---------------------------------------------------------------------------
# Relay — endpoint unificado para EARN y SPEND. El backend NO firma,
# solo reenvía transacciones YA FIRMADAS al NCT y registra en DB.
# ---------------------------------------------------------------------------


class RelayRequest(BaseModel):
    """Transacción completamente firmada que el backend solo reenvía al NCT.

    Tanto EARN como SPEND llegan por este mismo endpoint. La diferencia
    la determina `tx_type` y la valida el NCT (el EARN solo es aceptado
    si sender_pubkey == AUTHORITY_PUBKEY).
    """

    sender_pubkey: str = Field(description="64 hex chars — quien envía los tokens")
    receiver_pubkey: str = Field(description="64 hex chars — quien recibe los tokens")
    amount: int = Field(gt=0, le=1_000_000_000)
    tx_type: str = Field(description='"EARN" o "SPEND"')
    concept: str = Field(min_length=1, max_length=128)
    nonce: int = Field(ge=0)
    timestamp: float = Field(gt=0)
    signature: str = Field(description="128 hex chars — firma Ed25519 sobre tx_id")

    @field_validator("sender_pubkey")
    @classmethod
    def _validate_sender_pubkey(cls, v: str) -> str:
        from core.crypto import is_valid_pubkey_hex
        if not is_valid_pubkey_hex(v):
            raise ValueError("sender_pubkey debe ser 64 caracteres hex lowercase")
        return v

    @field_validator("receiver_pubkey")
    @classmethod
    def _validate_receiver_pubkey(cls, v: str) -> str:
        from core.crypto import is_valid_pubkey_hex
        if not is_valid_pubkey_hex(v):
            raise ValueError("receiver_pubkey debe ser 64 caracteres hex lowercase")
        return v

    @field_validator("tx_type")
    @classmethod
    def _validate_tx_type(cls, v: str) -> str:
        if v not in ("EARN", "SPEND"):
            raise ValueError('tx_type debe ser "EARN" o "SPEND"')
        return v

    @field_validator("signature")
    @classmethod
    def _validate_signature(cls, v: str) -> str:
        from core.crypto import is_valid_signature_hex
        if not is_valid_signature_hex(v):
            raise ValueError("signature debe ser 128 caracteres hex lowercase")
        return v


class RelayResponse(BaseModel):
    tx_id: str
    message: str = "Transacción aceptada por el NCT"


# ---------------------------------------------------------------------------
# Admin stats
# ---------------------------------------------------------------------------


class AdminStats(BaseModel):
    total_students: int
    total_vendors: int
    total_products: int
    total_purchases: int
    total_points_spent: int