"""AIS hook seams for cryptographic operations.

Track 1 default: NullAISCryptoHooks provides safe defaults / refuse-by-default
where no safe default exists. Track 2 implementations land at
backend/backend/immune/sec/crypto_backends.py (see jackpot_immune_platform_plan.md
§6.2.2 and §10.5).

Maps to:
- AIS §1.4 adaptive immunity (HE backend selection)
- AIS §1.7 attribution & deception (TEE attestation)
- AIS §1.8 tolerance/regulation (threshold signing, key rotation policy)

Direction of dependency is one-way: backend.crypto never imports from
backend.immune; backend.immune.sec.crypto_backends imports AISCryptoHooks
defined here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from backend.federation.models import FederatedInstance


class HEOperation(StrEnum):
    ADDITION = "addition"
    MULTIPLICATION = "multiplication"
    MASS_BALANCE = "mass_balance"  # cryptWWDB Use Case 1
    TIME_AWARE_MASS_BALANCE = "time_aware_mass_balance"  # cryptWWDB Use Case 2
    MEMORY_CELL_MATCH = "memory_cell_match"


class RotationAction(StrEnum):
    ALLOW = "allow"
    WARN = "warn"
    ROTATE_FIRST = "rotate_first"
    BLOCK = "block"


@dataclass(frozen=True)
class HEBackendSpec:
    backend_name: str
    scheme: str  # "CKKS" / "BFV" / "TFHE"
    params: tuple[tuple[str, int | float], ...]
    key_refs: tuple[str, ...]
    threat_model: str  # "single_key" / "multi_key"


@dataclass(frozen=True)
class ThresholdSignature:
    signature: bytes
    protocol: str  # "FROST" / "BLS-threshold"
    signers: tuple[str, ...]
    threshold_met: bool


@dataclass(frozen=True)
class Measurement:
    technology: str  # "SEV-SNP" / "TDX" / "TPM-2.0"
    pcr_index: int | None
    expected_hash: bytes


@dataclass(frozen=True)
class AttestationResult:
    verified: bool
    technology: str
    measurements: tuple[tuple[str, bytes], ...]
    expiry: datetime | None
    reason: str | None  # populated on verification failure


@dataclass(frozen=True)
class KeyReference:
    key_id: str
    key_type: str  # "federation_api" / "signing" / "encryption"
    keystore: str  # "secret_manager" / "pkcs11" / "filesystem"
    created_at: datetime


@runtime_checkable
class AISCryptoHooks(Protocol):
    """Extension surface for AIS-flavored cryptographic operations.

    Four hooks, mapped to four operator decision points:
      - select_he_backend     -> PRV-A `he_compute` Track 2 (HE scheme selection)
      - threshold_sign        -> FED-A `threshold_approve` Track 2 (M-of-N signing)
      - verify_tee_attestation-> FED-A `attest_partner` Track 2 (TEE evidence)
      - enforce_key_rotation_policy -> backend.crypto.keys load path

    Track 1 default: NullAISCryptoHooks (below). Track 2 implementations live
    at backend/backend/immune/sec/crypto_backends.py and are wired in via
    constructor DI on the relevant Track 1 classes.
    """

    def select_he_backend(
        self,
        operation: HEOperation,
        parties: tuple[FederatedInstance, ...] = (),
    ) -> HEBackendSpec:
        """Choose an HE backend for the given operation and party set.

        AIS doc:        §1.4 adaptive immunity (state-bearing computation)
        Track 2 impl:   backend/backend/immune/sec/crypto_backends.py
        Expertise:      applied cryptography (CKKS / BFV / TFHE selection,
                        multi-key vs single-key threat models per Driver
                        et al. 2024).

        Track 1 default (NullAISCryptoHooks): single-key TenSEAL CKKS with
        conservative params. Operators configure Track 2 for multi-key or
        scheme-specific tuning.
        """
        ...

    def threshold_sign(
        self,
        message: bytes,
        signers: tuple[FederatedInstance, ...],
        threshold: int,
    ) -> ThresholdSignature:
        """M-of-N threshold-signature production.

        AIS doc:        §1.8 tolerance/regulation (anti-autoimmune)
        Track 2 impl:   backend/backend/immune/sec/crypto_backends.py
                        (FROST / BLS-threshold primitives)
        Expertise:      applied cryptography (FROST, BLS-threshold, DKG).

        Track 1 default (NullAISCryptoHooks): refuses with NotImplementedError.
        Silent degradation to single-signer would defeat the governance
        purpose, so the default is explicit refusal.
        """
        ...

    def verify_tee_attestation(
        self,
        instance: FederatedInstance,
        evidence: bytes,
        expected_measurements: tuple[Measurement, ...] = (),
    ) -> AttestationResult:
        """Verify a partner's TEE remote-attestation evidence.

        AIS doc:        §1.7 attribution & deception
        Track 2 impl:   backend/backend/immune/sec/crypto_backends.py
                        (SEV-SNP / TDX / TPM-2.0 attestation verifiers)
        Expertise:      TEE / remote attestation, trusted-hardware
                        deployments.

        Track 1 default (NullAISCryptoHooks): returns AttestationResult with
        verified=False — trust-no-one until Track 2 is configured.
        """
        ...

    def enforce_key_rotation_policy(
        self,
        key_ref: KeyReference,
        key_age: timedelta,
        operation: str,
    ) -> RotationAction:
        """Decide whether to ALLOW/WARN/ROTATE_FIRST/BLOCK a key use.

        AIS doc:        §1.8 tolerance/regulation
        Track 2 impl:   backend/backend/immune/sec/crypto_backends.py
                        (operator-policy enforcement, age thresholds,
                        per-key-type policies).
        Expertise:      key-management policy + operator governance.

        Track 1 default (NullAISCryptoHooks): permissive — RotationAction.ALLOW.
        Operators opt into policy enforcement via Track 2.
        """
        ...


class NullAISCryptoHooks:
    """No-op / refuse-by-default crypto hooks. Operators configure Track 2
    implementations to enable cryptWWDB-track functionality.

    Behaviors:
      - select_he_backend: sensible default (single-key TenSEAL CKKS)
      - threshold_sign: raise NotImplementedError (no silent degradation)
      - verify_tee_attestation: return verified=False (trust-no-one)
      - enforce_key_rotation_policy: return RotationAction.ALLOW (permissive)
    """

    def select_he_backend(
        self,
        operation: HEOperation,
        parties: tuple[FederatedInstance, ...] = (),
    ) -> HEBackendSpec:
        return HEBackendSpec(
            backend_name="tenseal-ckks-default",
            scheme="CKKS",
            params=(("polynomial_modulus_degree", 8192), ("scale", float(2**40))),
            key_refs=(),
            threat_model="single_key",
        )

    def threshold_sign(
        self,
        message: bytes,
        signers: tuple[FederatedInstance, ...],
        threshold: int,
    ) -> ThresholdSignature:
        raise NotImplementedError(
            "Threshold signing requires Track 2 AISCryptoHooks implementation. "
            "Configure via backend/backend/immune/sec/crypto_backends.py."
        )

    def verify_tee_attestation(
        self,
        instance: FederatedInstance,
        evidence: bytes,
        expected_measurements: tuple[Measurement, ...] = (),
    ) -> AttestationResult:
        return AttestationResult(
            verified=False,
            technology="none",
            measurements=(),
            expiry=None,
            reason="No Track 2 attestation implementation configured",
        )

    def enforce_key_rotation_policy(
        self,
        key_ref: KeyReference,
        key_age: timedelta,
        operation: str,
    ) -> RotationAction:
        return RotationAction.ALLOW
