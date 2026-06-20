# DEO GLORIA

"""Cliente HTTP para el NCT (Nodo Coordinador de Transacciones) — Pilar 2.

Reemplaza por completo la implementación previa (placeholder), que usaba
nombres de campo y un modelo de identidad incompatibles con el NCT real:

    ANTES (incorrecto)          AHORA (NCT real)
    ----------------------      --------------------------------
    sender / receiver           sender_pubkey / receiver_pubkey (64 hex)
    type                        tx_type ("EARN" | "SPEND")
    (sin firma)                 signature (128 hex, Ed25519 sobre tx_id)
    (sin nonce)                 nonce (replay protection, por cuenta)
    "student:{legajo}" textual  pubkey real — el mapeo legajo↔pubkey lo
                                 resuelve este backend contra su propia DB,
                                 el NCT no conoce legajos ni vendor_ids.
    GET /balance/{student_id}   GET /balance/{pubkey} y GET /account/{pubkey}
    GET /transactions/{id}      (no existe en el NCT — el historial se
                                 mantiene localmente en transactions_log)

Dos flujos de firma MUY distintos:

- EARN: este backend conoce la clave PRIVADA de ACADEMIC_SYSTEM (vive en
  settings, nunca se loguea). `emit_earn()` arma la transacción completa:
  consulta el nonce vía /account, construye el signing dict, calcula
  tx_id, firma, y hace POST /transaction.

- SPEND: el backend NUNCA tiene la clave privada del estudiante — eso
  violaría el modelo de seguridad (la clave nunca debe salir del
  navegador). `emit_spend()` por lo tanto NO firma nada: recibe una
  transacción YA FIRMADA por el cliente (sender_pubkey, receiver_pubkey,
  amount, concept, nonce, timestamp, signature) y solo la reenvía al NCT.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from httpx import AsyncClient, HTTPError

from core.config import settings
from core.crypto import compute_tx_id, sign_message


class NCTError(Exception):
    """Error de comunicación con el NCT o transacción rechazada (400)."""

    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class NCTClient:
    """Cliente HTTP asíncrono para el NCT."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.nct_base_url
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
        """GET /account/{pubkey} → {"address", "balance", "nonce", "discarded_transactions"}.

        Este es el endpoint que SIEMPRE hay que consultar antes de firmar
        una transacción nueva, para obtener el `nonce` esperado.
        """
        try:
            response = await self.client.get(f"/account/{pubkey}")
            response.raise_for_status()
            return response.json()
        except HTTPError as exc:
            raise NCTError(f"Error consultando cuenta en el NCT: {exc}") from exc

    async def get_chain(self, start: int = 0, count: int = 20) -> list[dict]:
        """GET /chain?start=&count= → lista de bloques serializados (audit trail)."""
        try:
            response = await self.client.get(
                "/chain", params={"start": start, "count": count}
            )
            response.raise_for_status()
            return response.json()
        except HTTPError as exc:
            raise NCTError(f"Error consultando la cadena en el NCT: {exc}") from exc

    # ------------------------------------------------------------------
    # Escritura — POST /transaction
    # ------------------------------------------------------------------

    async def _post_transaction(self, payload: dict[str, Any]) -> dict:
        """POST /transaction crudo. Lanza NCTError con el mensaje del NCT en caso de 400."""
        response = await self.client.post("/transaction", json=payload)

        if response.status_code == 201:
            return response.json()

        # El NCT devuelve 400 con {"error": "..."} en validaciones fallidas
        # (firma inválida, nonce incorrecto, autoridad incorrecta, etc.)
        try:
            body = response.json()
            message = body.get("error", response.text)
        except Exception:
            message = response.text

        raise NCTError(message, status_code=response.status_code)

    async def emit_earn(self, *, receiver_pubkey: str, amount: int, concept: str) -> dict:
        """Emite una transacción EARN, firmada por este backend con la clave
        privada de ACADEMIC_SYSTEM (settings.academic_authority_private_key).

        El caller (router /admin/earn) es responsable de resolver
        `legajo -> receiver_pubkey` contra la tabla `users` ANTES de llamar
        a este método — este cliente no conoce legajos.

        `amount` es un entero (unidad mínima de puntos, como el "wei" de
        Ethereum) — así lo tipa `Transaction.amount: int` en shared/block.py.

        Devuelve {"tx_id": "..."} en éxito. Lanza NCTError en caso de
        rechazo (ej. nonce desincronizado, AUTHORITY_PUBKEY no configurada
        en el NCT, etc.)
        """
        sender_pubkey = settings.academic_authority_public_key
        if not sender_pubkey or not settings.academic_authority_private_key:
            raise NCTError(
                "ACADEMIC_AUTHORITY_PUBLIC_KEY / ACADEMIC_AUTHORITY_PRIVATE_KEY "
                "no están configuradas en el backend"
            )

        # 1. Nonce actual de la autoridad (puede haber avanzado por EARNs previos)
        account = await self.get_account(sender_pubkey)
        nonce = account["nonce"]

        # 2. Calcular tx_id — NOTA: timestamp NO participa del hash (ver
        #    shared/block.py Transaction._signing_dict: se fija
        #    server-side al llegar el POST, así que el cliente no puede
        #    predecirlo y se excluye deliberadamente del signing dict).
        #    El campo SÍ se manda en el wire payload (Transaction.from_dict
        #    lo lee), solo que no afecta tx_id ni la firma.
        tx_id = compute_tx_id(
            sender_pubkey=sender_pubkey,
            receiver_pubkey=receiver_pubkey,
            amount=amount,
            tx_type="EARN",
            concept=concept,
            nonce=nonce,
        )

        # 3. Firmar tx_id con la clave privada de la autoridad
        signature = sign_message(settings.academic_authority_private_key, tx_id)

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

    async def submit_signed_spend(
        self,
        *,
        sender_pubkey: str,
        receiver_pubkey: str,
        amount: int,
        concept: str,
        nonce: int,
        timestamp: float,
        signature: str,
    ) -> dict:
        """Reenvía al NCT una transacción SPEND YA FIRMADA por el cliente.

        Este método NO firma nada — la clave privada del estudiante nunca
        llega al backend. Todos los campos del signing dict (incluida la
        firma) vienen del frontend, que los calculó con exactamente la
        misma lógica que `core.crypto.compute_tx_id` (replica
        Transaction._signing_dict de shared/block.py: amount es int,
        timestamp NO participa del hash).

        El backend solo agrega tx_type="SPEND" y reenvía. La validación
        final y autoritativa (firma, nonce, saldo) la hace el NCT.
        """
        payload = {
            "sender_pubkey": sender_pubkey,
            "receiver_pubkey": receiver_pubkey,
            "amount": amount,
            "tx_type": "SPEND",
            "concept": concept,
            "nonce": nonce,
            "timestamp": timestamp,
            "signature": signature,
        }
        return await self._post_transaction(payload)

    # ------------------------------------------------------------------
    async def close(self):
        await self.client.aclose()


# Global NCT client instance
nct_client = NCTClient()