# DEO GLORIA

"""Tests unitarios para core/security.py.

Cubre: hashing de passwords, generación/validación de challenge,
firma del challenge, creación/decodificación de JWT.
Los tests de get_current_user / get_current_admin (que requieren DB)
se cubren de forma indirecta en los tests de routers.
"""

from __future__ import annotations

import time

import jwt
import pytest

from core.crypto import generate_keypair_hex, sign_message
from core.security import (
    AuthError,
    create_access_token,
    decode_access_token,
    generate_challenge,
    hash_password,
    validate_challenge_window,
    verify_challenge_signature,
    verify_password,
)


# ---------------------------------------------------------------------------
# hash_password / verify_password
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    def test_hash_returns_string(self):
        h = hash_password("mi_password_seguro")
        assert isinstance(h, str)

    def test_hash_starts_with_bcrypt_prefix(self):
        h = hash_password("test")
        assert h.startswith("$2b$")

    def test_hash_length_is_60(self):
        h = hash_password("test")
        assert len(h) == 60

    def test_same_password_produces_different_salts(self):
        h1 = hash_password("igual")
        h2 = hash_password("igual")
        assert h1 != h2  # bcrypt genera salt aleatorio

    def test_verify_correct_password(self):
        h = hash_password("correcto")
        assert verify_password("correcto", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("correcto")
        assert verify_password("incorrecto", h) is False

    def test_verify_malformed_hash_returns_false(self):
        # No debe lanzar excepción, solo devolver False
        assert verify_password("algo", "hash_mal_formado") is False

    def test_verify_empty_hash_returns_false(self):
        assert verify_password("algo", "") is False


# ---------------------------------------------------------------------------
# generate_challenge / validate_challenge_window
# ---------------------------------------------------------------------------

class TestChallenge:
    def test_generate_challenge_is_string_of_int(self):
        ch = generate_challenge()
        assert isinstance(ch, str)
        int(ch)  # debe ser parseable como int sin excepción

    def test_generate_challenge_is_recent(self):
        before = int(time.time())
        ch = generate_challenge()
        after = int(time.time())
        ts = int(ch)
        assert before <= ts <= after

    def test_validate_window_accepts_recent_challenge(self):
        ch = generate_challenge()
        result = validate_challenge_window(ch)
        assert isinstance(result, int)
        assert result == int(ch)

    def test_validate_window_rejects_future_challenge(self):
        future = str(int(time.time()) + 9999)
        with pytest.raises(AuthError, match="futuro"):
            validate_challenge_window(future)

    def test_validate_window_rejects_expired_challenge(self):
        expired = str(int(time.time()) - 9999)
        with pytest.raises(AuthError, match="expirado"):
            validate_challenge_window(expired)

    def test_validate_window_rejects_non_numeric(self):
        with pytest.raises(AuthError, match="no es un timestamp"):
            validate_challenge_window("no_es_numero")

    def test_validate_window_rejects_none(self):
        with pytest.raises(AuthError):
            validate_challenge_window(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# verify_challenge_signature
# ---------------------------------------------------------------------------

class TestVerifyChallengeSignature:
    def test_valid_signature_passes(self):
        priv, pub = generate_keypair_hex()
        ch = generate_challenge()
        sig = sign_message(priv, ch)
        # No debe lanzar excepción
        verify_challenge_signature(pub, ch, sig)

    def test_wrong_signature_raises_auth_error(self):
        priv, pub = generate_keypair_hex()
        _, other_priv_pub = generate_keypair_hex()
        ch = generate_challenge()
        # Firma con otra clave privada
        _, other_priv = generate_keypair_hex()
        bad_sig = sign_message(other_priv, ch)
        with pytest.raises(AuthError):
            verify_challenge_signature(pub, ch, bad_sig)

    def test_expired_challenge_raises_auth_error(self):
        priv, pub = generate_keypair_hex()
        expired = str(int(time.time()) - 9999)
        sig = sign_message(priv, expired)
        with pytest.raises(AuthError):
            verify_challenge_signature(pub, expired, sig)


# ---------------------------------------------------------------------------
# create_access_token / decode_access_token
# ---------------------------------------------------------------------------

class TestJWT:
    def _sample_token(self, user_id: int = 1, role: str = "student") -> str:
        _, pub = generate_keypair_hex()
        return create_access_token(
            user_id=user_id,
            legajo="TEST001",
            role=role,
            public_key=pub,
        )

    def test_create_returns_string(self):
        assert isinstance(self._sample_token(), str)

    def test_token_contains_expected_claims(self):
        _, pub = generate_keypair_hex()
        token = create_access_token(
            user_id=42,
            legajo="L42",
            role="admin",
            public_key=pub,
        )
        payload = decode_access_token(token)
        assert payload["sub"] == "42"
        assert payload["legajo"] == "L42"
        assert payload["role"] == "admin"
        assert payload["public_key"] == pub

    def test_decode_valid_token(self):
        token = self._sample_token()
        payload = decode_access_token(token)
        assert "sub" in payload
        assert "exp" in payload

    def test_decode_invalid_token_raises(self):
        with pytest.raises(Exception):
            decode_access_token("token.invalido.firma")

    def test_decode_empty_string_raises(self):
        with pytest.raises(Exception):
            decode_access_token("")

    def test_token_not_accepted_with_wrong_secret(self, monkeypatch):
        """Un token firmado con otro secret no debe decodificarse."""
        token = self._sample_token()
        # Decodificar con secret incorrecto debe fallar
        with pytest.raises(jwt.PyJWTError):
            jwt.decode(token, "secreto_incorrecto", algorithms=["HS256"])
