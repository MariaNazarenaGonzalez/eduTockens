# DEO GLORIA

"""Tests de integración para routers/products.py y routers/users.py."""

from __future__ import annotations

from models.models import Product
from tests.conftest import auth_headers


# ===========================================================================
# GET /health
# ===========================================================================

async def test_health_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ===========================================================================
# /api/products
# ===========================================================================

class TestListProducts:
    async def test_empty_db_returns_empty_list(self, client):
        resp = await client.get("/api/products")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_only_active_products(self, client, db_session, sample_vendor):
        inactive = Product(
            name="Inactivo",
            price_points=10,
            stock=5,
            active=False,
            vendor_id=sample_vendor.id,
        )
        active = Product(
            name="Activo",
            price_points=20,
            stock=5,
            active=True,
            vendor_id=sample_vendor.id,
        )
        db_session.add(inactive)
        db_session.add(active)
        await db_session.commit()

        resp = await client.get("/api/products")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "Activo" in names
        assert "Inactivo" not in names

    async def test_returns_vendor_pubkey(self, client, sample_product, sample_vendor):
        resp = await client.get("/api/products")
        assert resp.status_code == 200
        product = resp.json()[0]
        assert product["vendor_pubkey"] == sample_vendor.public_key


class TestGetProduct:
    async def test_existing_product_returns_200(self, client, sample_product):
        resp = await client.get(f"/api/products/{sample_product.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sample_product.id

    async def test_nonexistent_product_returns_404(self, client):
        resp = await client.get("/api/products/99999")
        assert resp.status_code == 404

    async def test_product_contains_required_fields(self, client, sample_product):
        resp = await client.get(f"/api/products/{sample_product.id}")
        body = resp.json()
        for field in ("id", "name", "price_points", "stock", "active", "vendor_id", "created_at"):
            assert field in body


class TestGetProductImage:
    async def test_product_without_image_returns_404(self, client, sample_product):
        resp = await client.get(f"/api/products/{sample_product.id}/image")
        assert resp.status_code == 404

    async def test_product_with_image_returns_bytes(self, client, db_session, sample_vendor):
        p = Product(
            name="Con imagen",
            price_points=10,
            stock=1,
            active=True,
            vendor_id=sample_vendor.id,
            image_data=b"\x89PNG fake",
            image_mime_type="image/png",
        )
        db_session.add(p)
        await db_session.commit()
        await db_session.refresh(p)

        resp = await client.get(f"/api/products/{p.id}/image")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"


# ===========================================================================
# GET /api/users/me
# ===========================================================================

class TestGetMe:
    async def test_without_token_returns_401(self, client):
        resp = await client.get("/api/users/me")
        assert resp.status_code == 401

    async def test_with_valid_token_returns_user(self, client, student_user):
        headers = auth_headers(student_user, "student")
        resp = await client.get("/api/users/me", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["legajo"] == student_user.legajo
        assert body["email"] == student_user.email
        assert body["role"] == "student"

    async def test_with_admin_token_returns_admin_role(self, client, admin_user):
        headers = auth_headers(admin_user, "admin")
        resp = await client.get("/api/users/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"
