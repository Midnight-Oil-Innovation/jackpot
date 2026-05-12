"""Signing primitives.

Two surfaces:
  - Ed25519Signer: fully functional Track 1 single-signer over the
    cryptography hazmat Ed25519 primitives. Loads key bytes from any
    KeystoreBackend.
  - threshold_sign: top-level delegate to the configured AISCryptoHooks
    threshold_sign hook. NullAISCryptoHooks raises; Track 2 implementations
    at backend/backend/immune/sec/crypto_backends.py provide real FROST /
    BLS-threshold.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from backend.crypto._ais_hooks import (
    AISCryptoHooks,
    NullAISCryptoHooks,
    ThresholdSignature,
)

if TYPE_CHECKING:
    from backend.crypto.keys import KeystoreBackend
    from backend.federation.models import FederatedInstance


class Ed25519Signer:
    """Track 1 single-signer using Ed25519.

    Reads a 32-byte Ed25519 private-key seed from the provided keystore.
    Sign/verify use the cryptography hazmat primitives directly so there's
    no third-party crypto dependency beyond `cryptography` itself.
    """

    SEED_LENGTH = 32

    def __init__(self, keystore: KeystoreBackend, key_id: str) -> None:
        self._keystore = keystore
        self._key_id = key_id

    def _load_private_key(self) -> ed25519.Ed25519PrivateKey:
        # FilesystemKeystore.load_key exposes operation= for the rotation
        # hook; callers of other keystores can ignore the kwarg.
        try:
            key_bytes = self._keystore.load_key(self._key_id, operation="sign")  # type: ignore[call-arg]
        except TypeError:
            key_bytes = self._keystore.load_key(self._key_id)
        if len(key_bytes) != self.SEED_LENGTH:
            raise ValueError(
                f"Ed25519 private key for {self._key_id!r} must be {self.SEED_LENGTH} bytes; "
                f"got {len(key_bytes)}"
            )
        return ed25519.Ed25519PrivateKey.from_private_bytes(key_bytes)

    def sign(self, message: bytes) -> bytes:
        return self._load_private_key().sign(message)

    @staticmethod
    def verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
        try:
            ed25519.Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
        except InvalidSignature:
            return False
        return True

    def public_key_bytes(self) -> bytes:
        from cryptography.hazmat.primitives import serialization

        return (
            self._load_private_key()
            .public_key()
            .public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        )


def threshold_sign(
    message: bytes,
    signers: tuple[FederatedInstance, ...],
    threshold: int,
    hooks: AISCryptoHooks | None = None,
) -> ThresholdSignature:
    """Delegate to AISCryptoHooks.threshold_sign.

    Track 1 default (NullAISCryptoHooks): raises NotImplementedError —
    threshold-signature governance requires explicit Track 2 configuration.
    Track 2 implementations supply real FROST / BLS-threshold protocols.
    """
    impl: AISCryptoHooks = hooks if hooks is not None else NullAISCryptoHooks()
    return impl.threshold_sign(message, signers, threshold)


__all__ = [
    "Ed25519Signer",
    "threshold_sign",
]
