# DEO GLORIA

"""Criptografía Ed25519 para eduTockens.

Este módulo centraliza las operaciones de clave pública que el backend
necesita para integrarse con el NCT:

- Verificar firmas (login/register de usuarios).
- Generar keypairs para vendors (se descarta la privada al instante).
- Calcular `tx_id` exactamente como lo hace el NCT (SHA-256 del signing
  dict canónico, sort_keys=True, incluyendo `nonce`).  El backend ya no
  firma transacciones — las wallets del frontend lo hacen.

Todas las claves/firmas se manejan como strings hex lowercase, igual que en
la wire format del NCT:
    - pubkey:    64 hex chars (32 bytes)
    - signature: 128 hex chars (64 bytes)
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX128_RE = re.compile(r"^[0-9a-f]{128}$")


class CryptoError(ValueError):
    """Error de validación criptográfica (formato o firma inválida)."""


# ---------------------------------------------------------------------------
# Validación de formato
# ---------------------------------------------------------------------------


def is_valid_pubkey_hex(value: str) -> bool:
    """True si `value` son 64 chars hex lowercase (clave pública Ed25519)."""
    return bool(_HEX64_RE.match(value))


def is_valid_signature_hex(value: str) -> bool:
    """True si `value` son 128 chars hex lowercase (firma Ed25519)."""
    return bool(_HEX128_RE.match(value))


# ---------------------------------------------------------------------------
# tx_id — debe coincidir EXACTAMENTE con el cálculo del NCT
# ---------------------------------------------------------------------------


def compute_tx_id(
    *,
    sender_pubkey: str,
    receiver_pubkey: str,
    amount: int,
    tx_type: str,
    concept: str,
    nonce: int,
) -> str:
    """Calcula `tx_id` = SHA-256(json.dumps(signing_dict, sort_keys=True)).

    Replica EXACTAMENTE `Transaction._signing_dict()` de shared/block.py
    (código real del NCT, no el doc de integración — que estaba desviado
    en dos puntos):

    1. `amount` es **int** (la unidad mínima, tipo "wei"), NO float. El
       propio dataclass de Transaction lo tipa como `amount: int` y su
       docstring dice explícitamente "Must be a positive integer".

    2. `timestamp` NO forma parte del signing dict. Se fija server-side
       al llegar el POST y el cliente no puede predecir el `time.time()`
       del NCT, así que el código real lo excluye deliberadamente
       (ver comentario en _signing_dict). El campo `timestamp` SÍ se
       manda en el JSON del POST /transaction (Transaction.from_dict lo
       lee), pero no participa del hash que se firma.

    El signing dict NUNCA incluye la firma — eso es lo que rompe la
    dependencia circular: hay que tener el tx_id antes de poder firmarlo.
    """
    signing_dict: dict[str, Any] = {
        "amount": int(amount),
        "concept": concept,
        "nonce": int(nonce),
        "receiver_pubkey": receiver_pubkey,
        "sender_pubkey": sender_pubkey,
        "tx_type": tx_type,
    }
    payload = json.dumps(signing_dict, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Firma institucional
# ---------------------------------------------------------------------------


def sign_message(private_key_hex: str, message: str) -> str:
    """Firma `message` (UTF-8) con una clave privada Ed25519.

    Usado exclusivamente para firmar EARN con la clave institucional
    de la universidad. La clave privada vive en `settings.authority_private_key`
    y nunca se expone.

    Devuelve la firma como 128 hex chars.
    """
    try:
        priv_bytes = bytes.fromhex(private_key_hex)
    except ValueError as exc:
        raise CryptoError(f"Clave privada inválida (no es hex): {exc}") from exc

    if len(priv_bytes) != 32:
        raise CryptoError(
            f"Clave privada debe ser 32 bytes (64 hex chars), se recibieron {len(priv_bytes)} bytes"
        )

    private_key = Ed25519PrivateKey.from_private_bytes(priv_bytes)
    signature = private_key.sign(message.encode("utf-8"))
    return signature.hex()


# ---------------------------------------------------------------------------
# Verificación de firmas
# ---------------------------------------------------------------------------


def verify_signature(public_key_hex: str, message: str, signature_hex: str) -> bool:
    """Verifica que `signature_hex` sea una firma Ed25519 válida de `message`
    (codificado a UTF-8) bajo `public_key_hex`.

    Usado para:
    - Verificar el challenge firmado en login/register.
    - (Si se necesitara) verificar firmas de SPEND antes de reenviar al NCT —
      aunque la verificación final y autoritativa siempre la hace el NCT.

    No lanza excepción en caso de firma inválida — devuelve False.
    Sí lanza CryptoError si el formato de los parámetros es inválido.
    """
    if not is_valid_pubkey_hex(public_key_hex):
        raise CryptoError(f"public_key debe ser 64 hex chars, got {len(public_key_hex)}")
    if not is_valid_signature_hex(signature_hex):
        raise CryptoError(f"signature debe ser 128 hex chars, got {len(signature_hex)}")

    pub_bytes = bytes.fromhex(public_key_hex)
    sig_bytes = bytes.fromhex(signature_hex)

    public_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
    try:
        public_key.verify(sig_bytes, message.encode("utf-8"))
        return True
    except InvalidSignature:
        return False


# ---------------------------------------------------------------------------
# Generación de keypairs (vendors)
# ---------------------------------------------------------------------------


def generate_keypair_hex() -> tuple[str, str]:
    """Genera un par Ed25519 nuevo. Devuelve (private_key_hex, public_key_hex).

    Usado exclusivamente para crear vendors: el caller debe usar la pubkey
    y DESCARTAR la privkey inmediatamente (no se persiste en ningún lado —
    el vendor nunca firma nada, es una dirección receptora pasiva).
    """
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_hex = private_key.private_bytes_raw().hex()
    pub_hex = public_key.public_bytes_raw().hex()

    return priv_hex, pub_hex