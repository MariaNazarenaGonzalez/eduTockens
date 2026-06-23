# DEO GLORIA

"""Tests de integración para routers/relay.py.

nct_client se mockea — el endpoint solo reenvía y registra.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from models.models import TransactionLog
from sqlalchemy import select
from tests.conftest import auth_headers
from core.crypto import generate_keypair_hex, sign_message


def _make_relay_body(sender_pubkey: str) -> dict:
    priv, _ = generate_keypair_hex()
    _, receiver_pub = generate_keypair_hex()
    sig = sign_message(priv, "tx_id_ficticio")
    return {
        "sender_pubkey": sender_pubkey,
        "receiver_pubkey": receiver_pub,
        "amount": 50,
        "tx_type": "SPEND",
        "concept": "Café",
        "nonce": 0,
        "timestamp": 1700000000.0,
        "signature": sig,
    }


class TestRelayTransaction:
    async def test_ok_returns_201(self, client, student_user):
        headers = auth_headers(student_user, "student")
        body = _make_relay_body(student_user.public_key)
        fake_tx_id = "g" * 64

        with patch("routers.relay.nct_client") as mock_nct:
            mock_nct.relay_transaction = AsyncMock(return_value={"tx_id": fake_tx_id})
            resp = await client.post("/api/transactions/relay", json=body, headers=headers)

        assert resp.status_code == 201
        assert resp.json()["tx_id"] == fake_tx_id

    async def test_transaction_log_created(self, client, student_user, db_session):
        headers = auth_headers(student_user, "student")
        body = _make_relay_body(student_user.public_key)
        fake_tx_id = "h" * 64

        with patch("routers.relay.nct_client") as mock_nct:
            mock_nct.relay_transaction = AsyncMock(return_value={"tx_id": fake_tx_id})
            await client.post("/api/transactions/relay", json=body, headers=headers)

        result = await db_session.execute(
            select(TransactionLog).where(TransactionLog.nct_tx_id == fake_tx_id)
        )
        log = result.scalar_one_or_none()
        assert log is not None
        assert log.tx_type == "SPEND"
        assert log.amount == 50

    async def test_nct_error_returns_400(self, client, student_user):
        from services.nct_client import NCTError
        headers = auth_headers(student_user, "student")
        body = _make_relay_body(student_user.public_key)

        with patch("routers.relay.nct_client") as mock_nct:
            mock_nct.relay_transaction = AsyncMock(
                side_effect=NCTError("Firma inválida", status_code=400)
            )
            resp = await client.post("/api/transactions/relay", json=body, headers=headers)

        assert resp.status_code == 400

    async def test_without_auth_returns_401(self, client, student_user):
        body = _make_relay_body(student_user.public_key)
        resp = await client.post("/api/transactions/relay", json=body)
        assert resp.status_code == 401

    async def test_unknown_sender_pubkey_no_log_created(self, client, student_user, db_session):
        """Si el sender_pubkey no corresponde a ningún User, no se crea TransactionLog."""
        headers = auth_headers(student_user, "student")
        # Usar una pubkey que no está en la DB
        _, unknown_pub = generate_keypair_hex()
        body = _make_relay_body(unknown_pub)
        fake_tx_id = "i" * 64

        with patch("routers.relay.nct_client") as mock_nct:
            mock_nct.relay_transaction = AsyncMock(return_value={"tx_id": fake_tx_id})
            resp = await client.post("/api/transactions/relay", json=body, headers=headers)

        assert resp.status_code == 201
        result = await db_session.execute(
            select(TransactionLog).where(TransactionLog.nct_tx_id == fake_tx_id)
        )
        # No debe existir log para pubkey desconocida
        assert result.scalar_one_or_none() is None
