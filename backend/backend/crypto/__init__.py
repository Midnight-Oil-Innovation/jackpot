"""JACKPOT crypto scaffold (CRY-A).

Sibling to backend/backend/federation/ (FED-A) and backend/backend/privacy/
(PRV-A). Establishes the `AISCryptoHooks` Protocol seam that PRV-A
`he_compute` and FED-A `threshold_approve` / `attest_partner` Track 2
implementations will consume.

Track 1 surface (functional):
  - FilesystemKeystore: 0600 file perms, JSON metadata sidecar, rotation-
    policy hook integration on load.
  - Ed25519Signer: single-signer sign/verify over hazmat primitives.

Track 2 surface (stubbed with NotImplementedError + explicit references):
  - SecretManagerKeystore (GCP integration sprint)
  - Pkcs11Keystore (hardware-token sprint)
  - Crypt4ghEncryptor (sequence-archive sprint; B-CRY-CRYPT4GH-1)
  - threshold_sign / TEE attestation (backend/backend/immune/sec/crypto_backends.py)

See README.md for the hook -> AIS-doc mapping table and the threat-model
note. Direction of dependency is one-way: backend.crypto never imports
from backend.immune.
"""

from backend.crypto._ais_hooks import (
    AISCryptoHooks,
    AttestationResult,
    HEBackendSpec,
    HEOperation,
    KeyReference,
    Measurement,
    NullAISCryptoHooks,
    RotationAction,
    ThresholdSignature,
)
from backend.crypto.crypt4gh import Crypt4ghEncryptor
from backend.crypto.keys import (
    FilesystemKeystore,
    KeystoreBackend,
    Pkcs11Keystore,
    SecretManagerKeystore,
    load_keystore,
)
from backend.crypto.signing import (
    Ed25519Signer,
    threshold_sign,
)

__all__ = [
    # Track 2 hook surface
    "AISCryptoHooks",
    "NullAISCryptoHooks",
    "HEBackendSpec",
    "HEOperation",
    "ThresholdSignature",
    "Measurement",
    "AttestationResult",
    "KeyReference",
    "RotationAction",
    # Track 1 keystore
    "KeystoreBackend",
    "FilesystemKeystore",
    "SecretManagerKeystore",
    "Pkcs11Keystore",
    "load_keystore",
    # Track 1 signing
    "Ed25519Signer",
    "threshold_sign",
    # Track 2 stubs
    "Crypt4ghEncryptor",
]
