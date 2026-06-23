# DEO GLORIA

"""Tests de integración para routers/auth.py.

Cubre: GET /challenge, POST /register, POST /login, POST /logout.
La firma Ed25519 del challenge es REAL (generada en el test),
garantizando que se ejercita todo el flujo criptográfico.
"""

from __future__ import annotations

import pytest

from core.crypto import generate_keypair_hex, sign_message
from core.security import generate_challenge, hash_password
from models.models import Role, User
from tests.conftest import auth_headers


# ---------------------------------------------------------------------------
# GET /api/auth/challenge
# ---------------------------------------------------------------------------

async def test_get_challenge_returns_200(client):
    resp = await client.get("/api/auth/challenge")
    assert resp.status_code == 200


async def test_get_challenge_returns_string_int(client):
    resp = await client.get("/api/auth/challenge")
    body = resp.json()
    assert "challenge" in body
    int(body["challenge"])  # debe ser convertible a int


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------

async def test_register_ok(client):
    priv, pub = generate_keypair_hex()
    ch_resp = await client.get("/api/auth/challenge")
    ch = ch_resp.json()["challenge"]
    sig = sign_message(priv, ch)

    resp = await client.post("/api/auth/register", json={
        "legajo": "REG001",
        "name": "Nuevo Estudiante",
        "email": "nuevo@unlu.edu.ar",
        "public_key": pub,
        "password": "password123",
        "challenge": ch,
        "signature": sig,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["legajo"] == "REG001"
    assert body["role"] == "student"


async def test_register_duplicate_legajo_returns_409(client):
    priv, pub = generate_keypair_hex()
    ch_resp = await client.get("/api/auth/challenge")
    ch = ch_resp.json()["challenge"]
    sig = sign_message(priv, ch)

    payload = {
        "legajo": "DUP001",
        "name": "Test",
        "email": "dup@unlu.edu.ar",
        "public_key": pub,
        "password": "password123",
        "challenge": ch,
        "signature": sig,
    }
    await client.post("/api/auth/register", json=payload)

    # Segundo intento con mismo legajo — nueva clave y sig para superar el challenge
    priv2, pub2 = generate_keypair_hex()
    ch_resp2 = await client.get("/api/auth/challenge")
    ch2 = ch_resp2.json()["challenge"]
    sig2 = sign_message(priv2, ch2)
    payload2 = {**payload, "public_key": pub2, "email": "otro@unlu.edu.ar",
                "challenge": ch2, "signature": sig2}
    resp = await client.post("/api/auth/register", json=payload2)
    assert resp.status_code == 409


async def test_register_invalid_signature_returns_400(client):
    _, pub = generate_keypair_hex()
    ch_resp = await client.get("/api/auth/challenge")
    ch = ch_resp.json()["challenge"]
    # Firma con otra clave privada
    other_priv, _ = generate_keypair_hex()
    bad_sig = sign_message(other_priv, ch)

    resp = await client.post("/api/auth/register", json={
        "legajo": "BAD001",
        "name": "Test",
        "email": "bad@unlu.edu.ar",
        "public_key": pub,
        "password": "password123",
        "challenge": ch,
        "signature": bad_sig,
    })
    assert resp.status_code == 400


async def test_register_missing_role_returns_500(client, db_session):
    """Si el rol 'student' no existe en la DB, el endpoint debe devolver 500."""
    from sqlalchemy import delete
    from models.models import Role
    await db_session.execute(delete(Role).where(Role.name == "student"))
    await db_session.commit()

    priv, pub = generate_keypair_hex()
    ch_resp = await client.get("/api/auth/challenge")
    ch = ch_resp.json()["challenge"]
    sig = sign_message(priv, ch)

    resp = await client.post("/api/auth/register", json={
        "legajo": "X001",
        "name": "Test",
        "email": "x@test.com",
        "public_key": pub,
        "password": "password123",
        "challenge": ch,
        "signature": sig,
    })
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

async def _register_user(client, legajo: str, email: str) -> tuple[str, str, str]:
    """Registra un usuario y devuelve (priv_hex, pub_hex, password)."""
    priv, pub = generate_keypair_hex()
    password = "login_pass123"
    ch_resp = await client.get("/api/auth/challenge")
    ch = ch_resp.json()["challenge"]
    sig = sign_message(priv, ch)
    await client.post("/api/auth/register", json={
        "legajo": legajo,
        "name": "Login Test",
        "email": email,
        "public_key": pub,
        "password": password,
        "challenge": ch,
        "signature": sig,
    })
    return priv, pub, password


async def test_login_ok(client):
    priv, pub, password = await _register_user(client, "L001", "login@test.com")
    ch_resp = await client.get("/api/auth/challenge")
    ch = ch_resp.json()["challenge"]
    sig = sign_message(priv, ch)

    resp = await client.post("/api/auth/login", json={
        "identifier": "L001",
        "password": password,
        "challenge": ch,
        "signature": sig,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["legajo"] == "L001"


async def test_login_wrong_password_returns_401(client):
    priv, _, _ = await _register_user(client, "L002", "l2@test.com")
    ch_resp = await client.get("/api/auth/challenge")
    ch = ch_resp.json()["challenge"]
    sig = sign_message(priv, ch)

    resp = await client.post("/api/auth/login", json={
        "identifier": "L002",
        "password": "password_incorrecta",
        "challenge": ch,
        "signature": sig,
    })
    assert resp.status_code == 401


async def test_login_unknown_user_returns_401(client):
    priv, _, _ = generate_keypair_hex(), None, None
    priv = generate_keypair_hex()[0]
    ch_resp = await client.get("/api/auth/challenge")
    ch = ch_resp.json()["challenge"]
    sig = sign_message(priv, ch)

    resp = await client.post("/api/auth/login", json={
        "identifier": "legajo_inexistente",
        "password": "cualquiera",
        "challenge": ch,
        "signature": sig,
    })
    assert resp.status_code == 401


async def test_login_wrong_challenge_signature_returns_401(client):
    priv, _, password = await _register_user(client, "L003", "l3@test.com")
    ch_resp = await client.get("/api/auth/challenge")
    ch = ch_resp.json()["challenge"]
    # Firma con otra clave
    other_priv = generate_keypair_hex()[0]
    bad_sig = sign_message(other_priv, ch)

    resp = await client.post("/api/auth/login", json={
        "identifier": "L003",
        "password": password,
        "challenge": ch,
        "signature": bad_sig,
    })
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------

async def test_logout_returns_ok(client):
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
