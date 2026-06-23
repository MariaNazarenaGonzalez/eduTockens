# DEO GLORIA

"""Tests de integración para routers/admin.py.

Todos los endpoints requieren rol 'admin'. Se verifica también que
usuarios sin token o con rol 'student' sean rechazados.
nct_client se mockea para emit_earn.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from models.models import Product, Purchase, TransactionLog, Vendor
from tests.conftest import auth_headers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_vendor_via_api(client, admin_headers, name: str = "Vendor") -> dict:
    resp = await client.post("/api/admin/vendors", json={"name": name}, headers=admin_headers)
    assert resp.status_code == 201
    return resp.json()


async def _create_product_via_api(client, admin_headers, vendor_id: int, name: str = "Producto") -> dict:
    resp = await client.post("/api/admin/products", json={
        "name": name,
        "price_points": 50,
        "stock": 10,
        "vendor_id": vendor_id,
    }, headers=admin_headers)
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Autorización: sin token / con rol student
# ---------------------------------------------------------------------------

class TestAdminAuthorization:
    async def test_no_token_returns_401(self, client):
        resp = await client.get("/api/admin/vendors")
        assert resp.status_code == 401

    async def test_student_role_returns_403(self, client, student_user):
        headers = auth_headers(student_user, "student")
        resp = await client.get("/api/admin/vendors", headers=headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Vendors
# ---------------------------------------------------------------------------

class TestAdminVendors:
    async def test_create_vendor_returns_201(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        resp = await client.post("/api/admin/vendors", json={"name": "Buffet"}, headers=headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Buffet"
        assert len(body["public_key"]) == 64  # hex64

    async def test_create_vendor_pubkey_is_valid_hex(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        resp = await client.post("/api/admin/vendors", json={"name": "Kiosco"}, headers=headers)
        pub = resp.json()["public_key"]
        assert all(c in "0123456789abcdef" for c in pub)

    async def test_list_vendors_empty(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        resp = await client.get("/api/admin/vendors", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_vendors_includes_created(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        await _create_vendor_via_api(client, headers, "Fotocopiadora")
        resp = await client.get("/api/admin/vendors", headers=headers)
        names = [v["name"] for v in resp.json()]
        assert "Fotocopiadora" in names


# ---------------------------------------------------------------------------
# Products (admin)
# ---------------------------------------------------------------------------

class TestAdminProducts:
    async def test_create_product_ok(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        vendor = await _create_vendor_via_api(client, headers)
        resp = await client.post("/api/admin/products", json={
            "name": "Café cortado",
            "price_points": 30,
            "stock": 20,
            "vendor_id": vendor["id"],
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["name"] == "Café cortado"

    async def test_create_product_vendor_not_found_returns_404(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        resp = await client.post("/api/admin/products", json={
            "name": "X",
            "price_points": 10,
            "vendor_id": 99999,
        }, headers=headers)
        assert resp.status_code == 404

    async def test_list_admin_products_includes_inactive(self, client, admin_user, db_session, sample_vendor):
        """Admin ve todos los productos, incluyendo los inactivos."""
        inactive = Product(
            name="Inactivo",
            price_points=5,
            active=False,
            vendor_id=sample_vendor.id,
        )
        db_session.add(inactive)
        await db_session.commit()

        headers = auth_headers(admin_user, "admin")
        resp = await client.get("/api/admin/products", headers=headers)
        names = [p["name"] for p in resp.json()]
        assert "Inactivo" in names

    async def test_update_product_ok(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        vendor = await _create_vendor_via_api(client, headers)
        product = await _create_product_via_api(client, headers, vendor["id"], "Original")

        resp = await client.put(f"/api/admin/products/{product['id']}", json={
            "name": "Actualizado",
            "price_points": 999,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Actualizado"
        assert resp.json()["price_points"] == 999

    async def test_update_product_not_found_returns_404(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        resp = await client.put("/api/admin/products/99999", json={"name": "X"}, headers=headers)
        assert resp.status_code == 404

    async def test_delete_product_ok(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        vendor = await _create_vendor_via_api(client, headers)
        product = await _create_product_via_api(client, headers, vendor["id"])

        resp = await client.delete(f"/api/admin/products/{product['id']}", headers=headers)
        assert resp.status_code == 204

        # Verificar que ya no existe
        get_resp = await client.get(f"/api/products/{product['id']}")
        assert get_resp.status_code == 404

    async def test_delete_product_not_found_returns_404(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        resp = await client.delete("/api/admin/products/99999", headers=headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# EARN
# ---------------------------------------------------------------------------

class TestAdminEarn:
    async def test_emit_earn_ok(self, client, admin_user, student_user):
        headers = auth_headers(admin_user, "admin")
        fake_tx_id = "e" * 64

        with patch("routers.admin.nct_client") as mock_nct:
            mock_nct.emit_earn = AsyncMock(return_value={"tx_id": fake_tx_id})
            resp = await client.post("/api/admin/earn", json={
                "legajo": student_user.legajo,
                "amount": 100,
                "concept": "Participación en clase",
            }, headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["tx_id"] == fake_tx_id
        assert body["legajo"] == student_user.legajo
        assert body["amount"] == 100

    async def test_emit_earn_student_not_found_returns_404(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        resp = await client.post("/api/admin/earn", json={
            "legajo": "LEGAJO_INEXISTENTE",
            "amount": 100,
            "concept": "X",
        }, headers=headers)
        assert resp.status_code == 404

    async def test_emit_earn_nct_error_returns_502(self, client, admin_user, student_user):
        from services.nct_client import NCTError
        headers = auth_headers(admin_user, "admin")

        with patch("routers.admin.nct_client") as mock_nct:
            mock_nct.emit_earn = AsyncMock(
                side_effect=NCTError("NCT error", status_code=400)
            )
            resp = await client.post("/api/admin/earn", json={
                "legajo": student_user.legajo,
                "amount": 50,
                "concept": "X",
            }, headers=headers)

        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestAdminStats:
    async def test_stats_returns_expected_shape(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        resp = await client.get("/api/admin/stats", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        for key in ("total_students", "total_vendors", "total_products",
                    "total_purchases", "total_points_spent"):
            assert key in body
            assert isinstance(body[key], int)

    async def test_stats_counts_student(self, client, admin_user, student_user):
        headers = auth_headers(admin_user, "admin")
        resp = await client.get("/api/admin/stats", headers=headers)
        assert resp.json()["total_students"] >= 1

    async def test_stats_total_points_spent_is_zero_when_no_purchases(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        resp = await client.get("/api/admin/stats", headers=headers)
        assert resp.json()["total_points_spent"] == 0


# ---------------------------------------------------------------------------
# Purchases log (admin)
# ---------------------------------------------------------------------------

class TestAdminPurchasesLog:
    async def test_returns_list(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        resp = await client.get("/api/admin/purchases", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_includes_purchase_data(self, client, admin_user, student_user, db_session, sample_product):
        purchase = Purchase(
            user_id=student_user.id,
            product_id=sample_product.id,
            points_spent=sample_product.price_points,
            nct_transaction_id="f" * 64,
        )
        db_session.add(purchase)
        await db_session.commit()

        headers = auth_headers(admin_user, "admin")
        resp = await client.get("/api/admin/purchases", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["legajo"] == student_user.legajo
