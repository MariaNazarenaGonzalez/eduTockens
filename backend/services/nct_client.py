# DEO GLORIA

"""Cliente HTTP para el NCT (Nodo Coordinador de Transacciones) — Pilar 2.

Único punto de contacto entre el backend de aplicación y la blockchain.
Dos modos de escritura:

  - EARN: el backend firma con la clave INSTITUCIONAL de la universidad
    (`emit_earn`). Esta clave no pertenece a ningún usuario persona —
    es la llave de emisión de la entidad académica.

  - SPEND: el backend solo reenvía al NCT transacciones YA FIRMADAS por
    la wallet del estudiante en el navegador (`relay_transaction`).

El NCT no conoce legajos, productos ni vendors — solo pubkeys.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from httpx import AsyncClient, HTTPError

from core.crypto import compute_tx_id, sign_message


class NCTError(Exception):
    """Error de comunicación con el NCT o transacción rechazada (400)."""

    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class NCTClient:
    """Cliente HTTP asíncrono para el NCT."""

    def __init__(self, base_url: str, authority_public_key: str = "", authority_private_key: str = ""):
        self.base_url = base_url
        self.authority_public_key = authority_public_key
        self.authority_private_key = authority_private_key
        self.client = AsyncClient(base_url=self.base_url, timeout=30.0)

    # ------------------------------------------------------------------
    # Lecturas
    # ------------------------------------------------------------------

    async def get_balance(self, pubkey: str) -> dict:
        """GET /balance/{pubkey} → {"address": ..., "balance": ...}"""
        try:
            response = await self.client.get(f"/balance/{pubkey}")
            response.raise_for_status()
            return response.json()
        except HTTPError as exc:
            raise NCTError(f"Error consultando balance en el NCT: {exc}") from exc

    async def get_account(self, pubkey: str) -> dict:
        """GET /account/{pubkey} → {"address", "balance", "nonce", "pending_nonce"}.

        IMPORTANTE: usar siempre ``pending_nonce`` (no ``nonce``) como nonce
        de la próxima transacción.
        """
        try:
            response = await self.client.get(f"/account/{pubkey}")
            response.raise_for_status()
            return response.json()
        except HTTPError as exc:
            raise NCTError(f"Error consultando cuenta en el NCT: {exc}") from exc

    async def get_chain(self, start: int = 0, count: int = 20) -> list[dict]:
        """GET /chain?start=&count= → lista de bloques serializados."""
        try:
            response = await self.client.get("/chain", params={"start": start, "count": count})
            response.raise_for_status()
            return response.json()
        except HTTPError as exc:
            raise NCTError(f"Error consultando la cadena en el NCT: {exc}") from exc

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    async def _post_transaction(self, payload: dict[str, Any]) -> dict:
        """POST /transaction crudo."""
        response = await self.client.post("/transaction", json=payload)
        if response.status_code == 201:
            return response.json()
        try:
            body = response.json()
            message = body.get("error", response.text)
        except Exception:
            message = response.text
        raise NCTError(message, status_code=response.status_code)

    async def emit_earn(
        self,
        *,
        receiver_pubkey: str,
        amount: int,
        concept: str,
        triggered_by_admin_id: int,
    ) -> dict:
        """Emite EARN firmado con la clave institucional de la universidad.

        El caller (router /admin/earn) es responsable de:
          1. Verificar que el admin está autenticado.
          2. Resolver `legajo → receiver_pubkey` contra la DB.
          3. Pasar `triggered_by_admin_id` para el audit trail.

        Devuelve {"tx_id": "..."} en éxito.
        """
        sender_pubkey = self.authority_public_key
        if not sender_pubkey or not self.authority_private_key:
            raise NCTError(
                "AUTHORITY_PUBLIC_KEY / AUTHORITY_PRIVATE_KEY no están configuradas en el backend"
            )

        # 1. Nonce actual de la autoridad
        account = await self.get_account(sender_pubkey)
        nonce = account["pending_nonce"]

        # 2. Calcular tx_id
        tx_id = compute_tx_id(
            sender_pubkey=sender_pubkey,
            receiver_pubkey=receiver_pubkey,
            amount=amount,
            tx_type="EARN",
            concept=concept,
            nonce=nonce,
        )

        # 3. Firmar con la clave institucional
        signature = sign_message(self.authority_private_key, tx_id)

        # 4. POST al NCT
        payload = {
            "sender_pubkey": sender_pubkey,
            "receiver_pubkey": receiver_pubkey,
            "amount": amount,
            "tx_type": "EARN",
            "concept": concept,
            "nonce": nonce,
            "timestamp": time.time(),
            "signature": signature,
        }
        return await self._post_transaction(payload)

    async def relay_transaction(self, payload: dict[str, Any]) -> dict:
        """Reenvía al NCT una transacción YA FIRMADA (SPEND del estudiante).

        El backend NO firma, NO valida la firma, NO resuelve legajos.
        Solo actúa como relay autenticado entre la wallet y el NCT.
        """
        return await self._post_transaction(payload)

    # ------------------------------------------------------------------
    async def close(self):
        await self.client.aclose()


# Global NCT client instance
from core.config import settings as _settings

nct_client = NCTClient(
    base_url=_settings.nct_base_url,
    authority_public_key=_settings.authority_public_key,
    authority_private_key=_settings.authority_private_key,
)
