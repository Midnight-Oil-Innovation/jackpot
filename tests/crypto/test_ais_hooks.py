# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Tests for the AISCryptoHooks Protocol + NullAISCryptoHooks default."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

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


def test_null_hooks_satisfies_protocol() -> None:
    assert isinstance(NullAISCryptoHooks(), AISCryptoHooks)


def test_select_he_backend_returns_sensible_default() -> None:
    hooks = NullAISCryptoHooks()
    spec = hooks.select_he_backend(HEOperation.MASS_BALANCE)

    assert isinstance(spec, HEBackendSpec)
    assert spec.scheme == "CKKS"
    assert spec.backend_name == "tenseal-ckks-default"
    assert spec.threat_model == "single_key"
    params = dict(spec.params)
    assert params["polynomial_modulus_degree"] == 8192
    assert params["scale"] == float(2**40)


def test_select_he_backend_with_parties_still_returns_default() -> None:
    hooks = NullAISCryptoHooks()
    spec = hooks.select_he_backend(HEOperation.TIME_AWARE_MASS_BALANCE, parties=())
    assert spec.scheme == "CKKS"


def test_threshold_sign_raises() -> None:
    hooks = NullAISCryptoHooks()
    with pytest.raises(NotImplementedError, match="Track 2 AISCryptoHooks"):
        hooks.threshold_sign(b"msg", (), 2)


def test_verify_tee_attestation_returns_unverified() -> None:
    hooks = NullAISCryptoHooks()
    result = hooks.verify_tee_attestation(instance=None, evidence=b"")  # type: ignore[arg-type]

    assert isinstance(result, AttestationResult)
    assert result.verified is False
    assert result.technology == "none"
    assert result.measurements == ()
    assert result.expiry is None
    assert result.reason and "Track 2" in result.reason


def test_enforce_key_rotation_policy_returns_allow() -> None:
    hooks = NullAISCryptoHooks()
    key_ref = KeyReference(
        key_id="k1",
        key_type="signing",
        keystore="filesystem",
        created_at=datetime.now(UTC),
    )
    action = hooks.enforce_key_rotation_policy(key_ref, timedelta(days=365), "sign")
    assert action == RotationAction.ALLOW


def test_he_operation_strenum_values() -> None:
    assert HEOperation.MASS_BALANCE.value == "mass_balance"
    assert HEOperation.TIME_AWARE_MASS_BALANCE.value == "time_aware_mass_balance"
    assert HEOperation.MEMORY_CELL_MATCH.value == "memory_cell_match"
    assert HEOperation.ADDITION.value == "addition"
    assert HEOperation.MULTIPLICATION.value == "multiplication"


def test_rotation_action_strenum_values() -> None:
    assert RotationAction.ALLOW.value == "allow"
    assert RotationAction.WARN.value == "warn"
    assert RotationAction.ROTATE_FIRST.value == "rotate_first"
    assert RotationAction.BLOCK.value == "block"


def test_he_backend_spec_frozen_and_hashable() -> None:
    spec = HEBackendSpec(
        backend_name="bn",
        scheme="CKKS",
        params=(("scale", 2.0),),
        key_refs=("k1",),
        threat_model="single_key",
    )
    with pytest.raises((AttributeError, TypeError)):
        spec.backend_name = "other"  # type: ignore[misc]
    assert hash(spec) == hash(spec)
    # Identical specs hash equal.
    spec2 = HEBackendSpec(
        backend_name="bn",
        scheme="CKKS",
        params=(("scale", 2.0),),
        key_refs=("k1",),
        threat_model="single_key",
    )
    assert spec == spec2
    assert hash(spec) == hash(spec2)


def test_threshold_signature_frozen_and_hashable() -> None:
    sig = ThresholdSignature(
        signature=b"\x00\x01",
        protocol="FROST",
        signers=("a", "b"),
        threshold_met=True,
    )
    with pytest.raises((AttributeError, TypeError)):
        sig.signature = b""  # type: ignore[misc]
    assert hash(sig) == hash(sig)


def test_measurement_frozen_and_hashable() -> None:
    m = Measurement(technology="SEV-SNP", pcr_index=0, expected_hash=b"\xff")
    with pytest.raises((AttributeError, TypeError)):
        m.technology = "TDX"  # type: ignore[misc]
    assert hash(m) == hash(m)


def test_attestation_result_frozen_and_hashable() -> None:
    r = AttestationResult(
        verified=True,
        technology="SEV-SNP",
        measurements=(("pcr0", b"\x01"),),
        expiry=None,
        reason=None,
    )
    with pytest.raises((AttributeError, TypeError)):
        r.verified = False  # type: ignore[misc]
    assert hash(r) == hash(r)


def test_key_reference_frozen_and_hashable() -> None:
    kr = KeyReference(
        key_id="k1",
        key_type="signing",
        keystore="filesystem",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with pytest.raises((AttributeError, TypeError)):
        kr.key_id = "other"  # type: ignore[misc]
    assert hash(kr) == hash(kr)
