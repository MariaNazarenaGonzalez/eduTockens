# DEO GLORIA

"""Tests de integración para routers/purchases.py.

nct_client se mockea para evitar llamadas reales al NCT.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from models.models import Product, Purchase
from tests.conftest import auth_headers


# ---------------------------------------------------------------------------
# POST /api/purchases
# ---------------------------------------------------------------------------

def _valid_purchase_payload(product_id: int, signature: str) -> dict:
    return {
        "product_id": product_id,
        "nonce": 0,
        "timestamp": 1700000000.0,
        "signature": signature,
    }


def _make_signature() -> str:
    from core.crypto import generate_keypair_hex, sign_message
    priv, _ = generate_keypair_hex()
    return sign_message(priv, "tx_id_ficticio")


class TestCreatePurchase:
    async def test_ok_returns_201(self, client, student_user, sample_product):
        headers = auth_headers(student_user, "student")
        fake_tx_id = "a" * 64

        with patch("routers.purchases.nct_client") as mock_nct:
            mock_nct.relay_transaction = AsyncMock(return_value={"tx_id": fake_tx_id})
            resp = await client.post(
                "/api/purchases",
                json=_valid_purchase_payload(sample_product.id, _make_signature()),
                headers=headers,
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["nct_transaction_id"] == fake_tx_id
        assert body["points_spent"] == sample_product.price_points

    async def test_product_not_found_returns_404(self, client, student_user):
        headers = auth_headers(student_user, "student")
        resp = await client.post(
            "/api/purchases",
            json=_valid_purchase_payload(99999, _make_signature()),
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_inactive_product_returns_404(self, client, student_user, db_session, sample_vendor):
        inactive = Product(
            name="Sin stock",
            price_points=10,
            stock=5,
            active=False,
            vendor_id=sample_vendor.id,
        )
        db_session.add(inactive)
        await db_session.commit()
        await db_session.refresh(inactive)

        headers = auth_headers(student_user, "student")
        resp = await client.post(
            "/api/purchases",
            json=_valid_purchase_payload(inactive.id, _make_signature()),
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_stock_zero_returns_400(self, client, student_user, db_session, sample_vendor):
        product = Product(
            name="Agotado",
            price_points=10,
            stock=0,
            active=True,
            vendor_id=sample_vendor.id,
        )
        db_session.add(product)
        await db_session.commit()
        await db_session.refresh(product)

        headers = auth_headers(student_user, "student")
        resp = await client.post(
            "/api/purchases",
            json=_valid_purchase_payload(product.id, _make_signature()),
            headers=headers,
        )
        assert resp.status_code == 400

    async def test_nct_error_returns_400(self, client, student_user, sample_product):
        from services.nct_client import NCTError
        headers = auth_headers(student_user, "student")

        with patch("routers.purchases.nct_client") as mock_nct:
            mock_nct.relay_transaction = AsyncMock(
                side_effect=NCTError("Saldo insuficiente", status_code=400)
            )
            resp = await client.post(
                "/api/purchases",
                json=_valid_purchase_payload(sample_product.id, _make_signature()),
                headers=headers,
            )

        assert resp.status_code == 400
        assert "Saldo insuficiente" in resp.json()["detail"]

    async def test_without_auth_returns_401(self, client, sample_product):
        resp = await client.post(
            "/api/purchases",
            json=_valid_purchase_payload(sample_product.id, _make_signature()),
        )
        assert resp.status_code == 401

    async def test_stock_decremented_after_purchase(self, client, student_user, db_session, sample_vendor):
        product = Product(
            name="Con stock",
            price_points=10,
            stock=5,
            active=True,
            vendor_id=sample_vendor.id,
        )
        db_session.add(product)
        await db_session.commit()
        await db_session.refresh(product)
        initial_stock = product.stock

        headers = auth_headers(student_user, "student")
        with patch("routers.purchases.nct_client") as mock_nct:
            mock_nct.relay_transaction = AsyncMock(return_value={"tx_id": "b" * 64})
            await client.post(
                "/api/purchases",
                json=_valid_purchase_payload(product.id, _make_signature()),
                headers=headers,
            )

        await db_session.refresh(product)
        assert product.stock == initial_stock - 1


# ---------------------------------------------------------------------------
# GET /api/purchases/me
# ---------------------------------------------------------------------------

class TestMyPurchases:
    async def test_no_purchases_returns_empty_list(self, client, student_user):
        headers = auth_headers(student_user, "student")
        resp = await client.get("/api/purchases/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_own_purchases(self, client, student_user, db_session, sample_product):
        purchase = Purchase(
            user_id=student_user.id,
            product_id=sample_product.id,
            points_spent=sample_product.price_points,
            nct_transaction_id="c" * 64,
        )
        db_session.add(purchase)
        await db_session.commit()

        headers = auth_headers(student_user, "student")
        resp = await client.get("/api/purchases/me", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["product_id"] == sample_product.id

    async def test_without_auth_returns_401(self, client):
        resp = await client.get("/api/purchases/me")
        assert resp.status_code == 401
