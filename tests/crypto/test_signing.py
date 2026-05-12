# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Tests for backend.crypto.signing."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from backend.crypto._ais_hooks import (
    HEBackendSpec,
    NullAISCryptoHooks,
    RotationAction,
    ThresholdSignature,
)
from backend.crypto.keys import FilesystemKeystore
from backend.crypto.signing import Ed25519Signer, threshold_sign


@pytest.fixture()
def signer(tmp_path: Path) -> Ed25519Signer:
    ks = FilesystemKeystore(directory=tmp_path / "keys")
    private_key = ed25519.Ed25519PrivateKey.generate()
    seed = private_key.private_bytes_raw()
    ks.store_key("alpha", seed, key_type="signing")
    return Ed25519Signer(ks, "alpha")


def test_ed25519_sign_and_verify(signer: Ed25519Signer) -> None:
    message = b"hello, federation"
    signature = signer.sign(message)
    public_key = signer.public_key_bytes()
    assert Ed25519Signer.verify(message, signature, public_key) is True


def test_ed25519_verify_fails_on_tampered_message(signer: Ed25519Signer) -> None:
    signature = signer.sign(b"original")
    public_key = signer.public_key_bytes()
    assert Ed25519Signer.verify(b"tampered", signature, public_key) is False


def test_ed25519_verify_fails_on_tampered_signature(signer: Ed25519Signer) -> None:
    message = b"original"
    signature = bytearray(signer.sign(message))
    signature[0] ^= 0xFF
    public_key = signer.public_key_bytes()
    assert Ed25519Signer.verify(message, bytes(signature), public_key) is False


def test_ed25519_rejects_wrong_seed_length(tmp_path: Path) -> None:
    ks = FilesystemKeystore(directory=tmp_path / "keys")
    ks.store_key("badlen", b"\x00" * 16, key_type="signing")
    s = Ed25519Signer(ks, "badlen")
    with pytest.raises(ValueError, match="must be 32 bytes"):
        s.sign(b"x")


def test_threshold_sign_default_null_hooks_raises() -> None:
    with pytest.raises(NotImplementedError, match="Track 2"):
        threshold_sign(b"msg", (), 2)


class _StubThresholdHooks:
    """Minimal Track-2-shaped hooks that return a fixed ThresholdSignature."""

    def select_he_backend(self, operation, parties=()):
        return HEBackendSpec(
            backend_name="x", scheme="CKKS", params=(), key_refs=(), threat_model="single_key"
        )

    def threshold_sign(self, message, signers, threshold):
        return ThresholdSignature(
            signature=b"stub-sig",
            protocol="FROST",
            signers=tuple(f"signer{i}" for i in range(len(signers))),
            threshold_met=len(signers) >= threshold,
        )

    def verify_tee_attestation(self, instance, evidence, expected_measurements=()):
        raise NotImplementedError

    def enforce_key_rotation_policy(self, key_ref, key_age, operation):
        return RotationAction.ALLOW


def test_threshold_sign_with_track2_hooks_returns_signature() -> None:
    hooks = _StubThresholdHooks()
    sig = threshold_sign(b"msg", (object(), object(), object()), 2, hooks=hooks)
    assert isinstance(sig, ThresholdSignature)
    assert sig.protocol == "FROST"
    assert sig.threshold_met is True
    assert sig.signature == b"stub-sig"


def test_threshold_sign_explicit_null_hooks_raises() -> None:
    with pytest.raises(NotImplementedError):
        threshold_sign(b"m", (), 1, hooks=NullAISCryptoHooks())


def test_ed25519_signer_works_against_plain_keystore_without_kwarg(tmp_path: Path) -> None:
    """Backends that don't accept operation= kwarg still work (TypeError fallback)."""

    class _PlainKS:
        def __init__(self, store: dict[str, bytes]) -> None:
            self._store = store

        def load_key(self, key_id: str) -> bytes:
            return self._store[key_id]

        def store_key(self, key_id, key_bytes, *, key_type="signing"):
            self._store[key_id] = key_bytes

        def list_keys(self):
            return list(self._store)

        def delete_key(self, key_id):
            del self._store[key_id]

    sk = ed25519.Ed25519PrivateKey.generate()
    ks = _PlainKS({"k": sk.private_bytes_raw()})
    signer = Ed25519Signer(ks, "k")  # type: ignore[arg-type]
    message = b"hello"
    signature = signer.sign(message)
    assert Ed25519Signer.verify(message, signature, signer.public_key_bytes())
