"""GA4GH Crypt4GH per-file encryption interface.

This module is interface-only. Real integration with the GA4GH Crypt4GH
standard (https://samtools.github.io/hts-specs/crypt4gh.html) is deferred
to the Track 2 sequence-archive sprint and tracked as B-CRY-CRYPT4GH-1.

The shape mirrors what the real implementation will expose, so callers can
swap in the concrete encryptor without changing call sites once the
sequence-archive sprint lands.
"""

from __future__ import annotations

from pathlib import Path

_DEFERRED_REASON = (
    "GA4GH Crypt4GH integration deferred to Track 2 / sequence-archive sprint. "
    "Tracked as B-CRY-CRYPT4GH-1 follow-up."
)


class Crypt4ghEncryptor:
    """Per-file Crypt4GH encryption / decryption. Stubbed pending Track 2.

    Methods raise NotImplementedError until the sequence-archive sprint
    delivers the concrete implementation backed by the `crypt4gh` Python
    library or an equivalent GA4GH-conformant codec.
    """

    def encrypt_file(
        self,
        input_path: Path,
        output_path: Path,
        recipient_public_keys: tuple[bytes, ...],
    ) -> None:
        raise NotImplementedError(_DEFERRED_REASON)

    def decrypt_file(
        self,
        input_path: Path,
        output_path: Path,
        recipient_private_key: bytes,
    ) -> None:
        raise NotImplementedError(_DEFERRED_REASON)


__all__ = ["Crypt4ghEncryptor"]
