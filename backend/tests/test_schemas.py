# DEO GLORIA

"""Tests de validación para schemas/schemas.py (Pydantic).

No requieren DB ni red — solo instanciación de modelos Pydantic
y verificación de ValidationError cuando los datos son inválidos.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.crypto import generate_keypair_hex, sign_message
from core.security import generate_challenge
from schemas.schemas import (
    EarnRequest,
    LoginRequest,
    ProductCreate,
    ProductUpdate,
    PurchaseCreate,
    RegisterRequest,
    RelayRequest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_register_body() -> dict:
    priv, pub = generate_keypair_hex()
    ch = generate_challenge()
    sig = sign_message(priv, ch)
    return {
        "legajo": "S00001",
        "name": "Ana García",
        "email": "ana@unlu.edu.ar",
        "public_key": pub,
        "password": "password_seguro",
        "challenge": ch,
        "signature": sig,
    }


def _make_valid_relay_body() -> dict:
    priv_s, pub_s = generate_keypair_hex()
    _, pub_r = generate_keypair_hex()
    # tx_id ficticio firmado con clave del sender
    tx_id = "a" * 64
    sig = sign_message(priv_s, tx_id)
    return {
        "sender_pubkey": pub_s,
        "receiver_pubkey": pub_r,
        "amount": 100,
        "tx_type": "SPEND",
        "concept": "Café",
        "nonce": 0,
        "timestamp": 1700000000.0,
        "signature": sig,
    }


# ---------------------------------------------------------------------------
# RegisterRequest
# ---------------------------------------------------------------------------

class TestRegisterRequest:
    def test_valid_body_creates_instance(self):
        body = RegisterRequest(**_make_valid_register_body())
        assert body.legajo == "S00001"

    def test_invalid_pubkey_not_hex(self):
        data = _make_valid_register_body()
        data["public_key"] = "no_es_hex_" + "x" * 54
        with pytest.raises(ValidationError, match="hex"):
            RegisterRequest(**data)

    def test_invalid_pubkey_uppercase(self):
        data = _make_valid_register_body()
        data["public_key"] = data["public_key"].upper()
        with pytest.raises(ValidationError):
            RegisterRequest(**data)

    def test_invalid_pubkey_wrong_length(self):
        data = _make_valid_register_body()
        data["public_key"] = "ab" * 30  # 60 chars, no 64
        with pytest.raises(ValidationError):
            RegisterRequest(**data)

    def test_invalid_signature_wrong_length(self):
        data = _make_valid_register_body()
        data["signature"] = "ab" * 60  # 120 chars, no 128
        with pytest.raises(ValidationError):
            RegisterRequest(**data)

    def test_password_too_short(self):
        data = _make_valid_register_body()
        data["password"] = "corto"  # < 8 chars
        with pytest.raises(ValidationError):
            RegisterRequest(**data)

    def test_legajo_empty_fails(self):
        data = _make_valid_register_body()
        data["legajo"] = ""
        with pytest.raises(ValidationError):
            RegisterRequest(**data)


# ---------------------------------------------------------------------------
# LoginRequest
# ---------------------------------------------------------------------------

class TestLoginRequest:
    def test_valid_body(self):
        priv, _ = generate_keypair_hex()
        ch = generate_challenge()
        sig = sign_message(priv, ch)
        body = LoginRequest(
            identifier="student@test.com",
            password="password123",
            challenge=ch,
            signature=sig,
        )
        assert body.identifier == "student@test.com"

    def test_empty_password_fails(self):
        priv, _ = generate_keypair_hex()
        ch = generate_challenge()
        sig = sign_message(priv, ch)
        with pytest.raises(ValidationError):
            LoginRequest(identifier="x", password="", challenge=ch, signature=sig)


# ---------------------------------------------------------------------------
# PurchaseCreate
# ---------------------------------------------------------------------------

class TestPurchaseCreate:
    def _valid_sig(self) -> str:
        priv, _ = generate_keypair_hex()
        return sign_message(priv, "tx_id_ficticio")

    def test_valid_body(self):
        body = PurchaseCreate(
            product_id=1,
            nonce=0,
            timestamp=1700000000.0,
            signature=self._valid_sig(),
        )
        assert body.product_id == 1

    def test_negative_nonce_fails(self):
        with pytest.raises(ValidationError):
            PurchaseCreate(
                product_id=1,
                nonce=-1,
                timestamp=1700000000.0,
                signature=self._valid_sig(),
            )

    def test_invalid_signature_fails(self):
        with pytest.raises(ValidationError):
            PurchaseCreate(
                product_id=1,
                nonce=0,
                timestamp=1700000000.0,
                signature="firma_invalida",
            )


# ---------------------------------------------------------------------------
# RelayRequest
# ---------------------------------------------------------------------------

class TestRelayRequest:
    def test_valid_body(self):
        body = RelayRequest(**_make_valid_relay_body())
        assert body.tx_type == "SPEND"

    def test_invalid_tx_type(self):
        data = _make_valid_relay_body()
        data["tx_type"] = "TRANSFER"
        with pytest.raises(ValidationError, match="EARN.*SPEND|tx_type"):
            RelayRequest(**data)

    def test_invalid_sender_pubkey(self):
        data = _make_valid_relay_body()
        data["sender_pubkey"] = "pubkey_corta"
        with pytest.raises(ValidationError):
            RelayRequest(**data)

    def test_invalid_receiver_pubkey(self):
        data = _make_valid_relay_body()
        data["receiver_pubkey"] = "X" * 64  # mayúsculas
        with pytest.raises(ValidationError):
            RelayRequest(**data)

    def test_amount_zero_fails(self):
        data = _make_valid_relay_body()
        data["amount"] = 0
        with pytest.raises(ValidationError):
            RelayRequest(**data)


# ---------------------------------------------------------------------------
# EarnRequest
# ---------------------------------------------------------------------------

class TestEarnRequest:
    def test_valid_body(self):
        body = EarnRequest(legajo="S001", amount=100, concept="Participación")
        assert body.amount == 100

    def test_amount_zero_fails(self):
        with pytest.raises(ValidationError):
            EarnRequest(legajo="S001", amount=0, concept="x")

    def test_concept_empty_fails(self):
        with pytest.raises(ValidationError):
            EarnRequest(legajo="S001", amount=100, concept="")


# ---------------------------------------------------------------------------
# ProductCreate / ProductUpdate
# ---------------------------------------------------------------------------

class TestProductSchemas:
    def test_product_create_valid(self):
        p = ProductCreate(name="Café", price_points=50, vendor_id=1)
        assert p.price_points == 50

    def test_product_create_price_zero_fails(self):
        with pytest.raises(ValidationError):
            ProductCreate(name="Café", price_points=0, vendor_id=1)

    def test_product_update_all_optional(self):
        # Ningún campo obligatorio — body vacío es válido
        p = ProductUpdate()
        assert p.name is None
