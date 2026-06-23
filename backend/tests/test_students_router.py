# DEO GLORIA

"""Tests de integración para routers/students.py.

nct_client se mockea — los tests no requieren el NCT real.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from models.models import TransactionLog
from tests.conftest import auth_headers


MOCK_ACCOUNT = {
    "address": "pubkey_hex",
    "balance": 500,
    "nonce": 3,
    "pending_nonce": 4,
}


# ---------------------------------------------------------------------------
# GET /api/students/{legajo}/balance
# ---------------------------------------------------------------------------

class TestGetBalance:
    async def test_ok_returns_balance(self, client, student_user):
        with patch("routers.students.nct_client") as mock_nct:
            mock_nct.get_account = AsyncMock(return_value=MOCK_ACCOUNT)
            resp = await client.get(f"/api/students/{student_user.legajo}/balance")

        assert resp.status_code == 200
        body = resp.json()
        assert body["legajo"] == student_user.legajo
        assert body["balance"] == 500
        assert body["nonce"] == 3
        assert body["pending_nonce"] == 4
        assert body["public_key"] == student_user.public_key

    async def test_nonexistent_legajo_returns_404(self, client):
        resp = await client.get("/api/students/LEGAJO_INEXISTENTE/balance")
        assert resp.status_code == 404

    async def test_nct_error_returns_502(self, client, student_user):
        from services.nct_client import NCTError
        with patch("routers.students.nct_client") as mock_nct:
            mock_nct.get_account = AsyncMock(
                side_effect=NCTError("NCT no disponible")
            )
            resp = await client.get(f"/api/students/{student_user.legajo}/balance")

        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# GET /api/students/{legajo}/transactions
# ---------------------------------------------------------------------------

class TestGetTransactions:
    async def test_no_transactions_returns_empty_list(self, client, student_user):
        resp = await client.get(f"/api/students/{student_user.legajo}/transactions")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_student_transactions(self, client, student_user, db_session, sample_vendor):
        log = TransactionLog(
            user_id=student_user.id,
            tx_type="EARN",
            counterparty_pubkey=sample_vendor.public_key,
            amount=100,
            concept="Premio asistencia",
            nct_tx_id="d" * 64,
        )
        db_session.add(log)
        await db_session.commit()

        resp = await client.get(f"/api/students/{student_user.legajo}/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["tx_type"] == "EARN"
        assert data[0]["amount"] == 100
        assert data[0]["concept"] == "Premio asistencia"

    async def test_nonexistent_legajo_returns_404(self, client):
        resp = await client.get("/api/students/NO_EXISTE/transactions")
        assert resp.status_code == 404