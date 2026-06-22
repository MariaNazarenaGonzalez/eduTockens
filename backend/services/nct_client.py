# DEO GLORIA

"""Cliente HTTP para el NCT (Nodo Coordinador de Transacciones) — Pilar 2.

Único punto de contacto entre el backend de aplicación y la blockchain.
El backend NO conoce claves privadas — las wallets del frontend firman
EARN y SPEND, y este cliente solo:

  - Consulta balances y cuentas (GET /balance, GET /account).
  - Reenvía transacciones YA FIRMADAS al NCT (POST /transaction vía
    relay_transaction).

El NCT no conoce legajos, productos ni vendors — solo pubkeys.
"""

from __future__ import annotations

from typing import Any, Optional

from httpx import AsyncClient, HTTPError


class NCTError(Exception):
    """Error de comunicación con el NCT o transacción rechazada (400)."""

    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class NCTClient:
    """Cliente HTTP asíncrono para el NCT (sin claves privadas)."""

    def __init__(self, base_url: str, authority_public_key: str = ""):
        self.base_url = base_url
        self.authority_public_key = authority_public_key
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
        """GET /account/{pubkey} → {"address", "balance", "nonce", "pending_nonce", "discarded_transactions"}.

        Este es el endpoint que SIEMPRE hay que consultar antes de firmar
        una transacción nueva.

        IMPORTANTE: usar siempre ``pending_nonce`` (no ``nonce``) como nonce
        de la próxima transacción. ``pending_nonce`` considera las transacciones
        que ya enviaste y están en el pool; ``nonce`` es el confirmado en cadena
        y solo avanza cuando se mina un bloque. Usar ``nonce`` cuando hay
        transacciones pendientes produce error de replay.
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
    # Escritura unificada — POST /transaction
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

    async def relay_transaction(self, payload: dict[str, Any]) -> dict:
        """Reenvía al NCT una transacción YA FIRMADA, sin distinguir EARN de SPEND.

        Este es el método unificado de escritura. Recibe el payload completo
        tal como lo construyó la wallet del frontend (todos los campos del
        signing dict + signature + timestamp) y lo reenvía textualmente al
        NCT vía POST /transaction.

        El backend NO firma, NO valida la firma, NO resuelve legajos. Solo
        actúa como relay autenticado entre la wallet y el NCT.
        """
        return await self._post_transaction(payload)

    # ------------------------------------------------------------------
    async def close(self):
        await self.client.aclose()


# Global NCT client instance (sin clave privada)
from core.config import settings as _settings

nct_client = NCTClient(
    base_url=_settings.nct_base_url,
    authority_public_key=_settings.authority_public_key,
)
