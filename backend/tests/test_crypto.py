# DEO GLORIA

"""Tests unitarios para core/crypto.py.

No requieren DB ni red — son funciones puras de criptografía.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.crypto import (
    CryptoError,
    compute_tx_id,
    generate_keypair_hex,
    is_valid_pubkey_hex,
    is_valid_signature_hex,
    sign_message,
    verify_signature,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_keypair() -> tuple[str, str]:
    """Genera un par Ed25519 y devuelve (priv_hex, pub_hex)."""
    priv, pub = generate_keypair_hex()
    return priv, pub


# ---------------------------------------------------------------------------
# is_valid_pubkey_hex
# ---------------------------------------------------------------------------

class TestIsValidPubkeyHex:
    def test_valid_hex_64(self):
        _, pub = _make_keypair()
        assert is_valid_pubkey_hex(pub) is True

    def test_invalid_63_chars(self):
        _, pub = _make_keypair()
        assert is_valid_pubkey_hex(pub[:-1]) is False

    def test_invalid_65_chars(self):
        _, pub = _make_keypair()
        assert is_valid_pubkey_hex(pub + "a") is False

    def test_invalid_uppercase(self):
        _, pub = _make_keypair()
        assert is_valid_pubkey_hex(pub.upper()) is False

    def test_invalid_non_hex_chars(self):
        assert is_valid_pubkey_hex("g" * 64) is False

    def test_invalid_empty(self):
        assert is_valid_pubkey_hex("") is False


# ---------------------------------------------------------------------------
# is_valid_signature_hex
# ---------------------------------------------------------------------------

class TestIsValidSignatureHex:
    def test_valid_hex_128(self):
        priv, _ = _make_keypair()
        sig = sign_message(priv, "mensaje")
        assert is_valid_signature_hex(sig) is True

    def test_invalid_127_chars(self):
        priv, _ = _make_keypair()
        sig = sign_message(priv, "mensaje")
        assert is_valid_signature_hex(sig[:-1]) is False

    def test_invalid_uppercase(self):
        priv, _ = _make_keypair()
        sig = sign_message(priv, "mensaje")
        assert is_valid_signature_hex(sig.upper()) is False

    def test_invalid_empty(self):
        assert is_valid_signature_hex("") is False


# ---------------------------------------------------------------------------
# compute_tx_id
# ---------------------------------------------------------------------------

class TestComputeTxId:
    def _base_kwargs(self) -> dict:
        _, sender = _make_keypair()
        _, receiver = _make_keypair()
        return dict(
            sender_pubkey=sender,
            receiver_pubkey=receiver,
            amount=100,
            tx_type="EARN",
            concept="Premio",
            nonce=0,
        )

    def test_deterministic(self):
        kwargs = self._base_kwargs()
        assert compute_tx_id(**kwargs) == compute_tx_id(**kwargs)

    def test_returns_hex_64(self):
        result = compute_tx_id(**self._base_kwargs())
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_sort_keys_order(self):
        """El hash debe coincidir con SHA-256 del JSON con sort_keys=True."""
        kwargs = self._base_kwargs()
        signing_dict = {
            "amount": int(kwargs["amount"]),
            "concept": kwargs["concept"],
            "nonce": int(kwargs["nonce"]),
            "receiver_pubkey": kwargs["receiver_pubkey"],
            "sender_pubkey": kwargs["sender_pubkey"],
            "tx_type": kwargs["tx_type"],
        }
        expected = hashlib.sha256(
            json.dumps(signing_dict, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        assert compute_tx_id(**kwargs) == expected

    def test_different_amount_yields_different_hash(self):
        kwargs = self._base_kwargs()
        h1 = compute_tx_id(**kwargs)
        kwargs["amount"] = 999
        h2 = compute_tx_id(**kwargs)
        assert h1 != h2

    def test_amount_coerced_to_int(self):
        """amount=100 y amount=100.0 deben producir el mismo hash."""
        kwargs = self._base_kwargs()
        h_int = compute_tx_id(**kwargs)
        kwargs["amount"] = 100.0  # type: ignore[arg-type]
        h_float = compute_tx_id(**kwargs)
        assert h_int == h_float


# ---------------------------------------------------------------------------
# generate_keypair_hex
# ---------------------------------------------------------------------------

class TestGenerateKeypairHex:
    def test_returns_tuple_of_two_hex64(self):
        priv, pub = generate_keypair_hex()
        assert len(priv) == 64
        assert len(pub) == 64
        assert all(c in "0123456789abcdef" for c in priv)
        assert all(c in "0123456789abcdef" for c in pub)

    def test_each_call_returns_different_keys(self):
        priv1, pub1 = generate_keypair_hex()
        priv2, pub2 = generate_keypair_hex()
        assert priv1 != priv2
        assert pub1 != pub2

    def test_priv_and_pub_are_different(self):
        priv, pub = generate_keypair_hex()
        assert priv != pub


# ---------------------------------------------------------------------------
# sign_message / verify_signature (round-trip)
# ---------------------------------------------------------------------------

class TestSignAndVerify:
    def test_roundtrip_ok(self):
        priv, pub = _make_keypair()
        sig = sign_message(priv, "hola mundo")
        assert verify_signature(pub, "hola mundo", sig) is True

    def test_wrong_message_fails(self):
        priv, pub = _make_keypair()
        sig = sign_message(priv, "mensaje original")
        assert verify_signature(pub, "mensaje distinto", sig) is False

    def test_wrong_pubkey_fails(self):
        priv, _ = _make_keypair()
        _, other_pub = _make_keypair()
        sig = sign_message(priv, "hola")
        assert verify_signature(other_pub, "hola", sig) is False

    def test_tampered_signature_fails(self):
        priv, pub = _make_keypair()
        sig = sign_message(priv, "hola")
        # Alterar el último byte de la firma
        tampered = sig[:-2] + ("00" if sig[-2:] != "00" else "ff")
        assert verify_signature(pub, "hola", tampered) is False

    def test_sign_invalid_private_key_raises(self):
        with pytest.raises(CryptoError, match="hex"):
            sign_message("clave_no_hex", "hola")

    def test_sign_wrong_length_raises(self):
        with pytest.raises(CryptoError, match="32 bytes"):
            sign_message("ab" * 16, "hola")  # 16 bytes en lugar de 32

    def test_verify_invalid_pubkey_format_raises(self):
        _, pub = _make_keypair()
        priv2, _ = _make_keypair()
        sig = sign_message(priv2, "x")
        with pytest.raises(CryptoError):
            verify_signature("pubkey_corta", "x", sig)

    def test_verify_invalid_signature_format_raises(self):
        _, pub = _make_keypair()
        with pytest.raises(CryptoError):
            verify_signature(pub, "x", "firma_corta")
