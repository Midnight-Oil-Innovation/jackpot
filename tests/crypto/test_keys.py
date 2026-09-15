# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Tests for backend.crypto.keys."""

from __future__ import annotations

import json
import logging
import os
import stat
from datetime import timedelta
from pathlib import Path

import pytest

from backend.crypto._ais_hooks import (
    AISCryptoHooks,
    HEBackendSpec,
    KeyReference,
    NullAISCryptoHooks,
    RotationAction,
    ThresholdSignature,
)
from backend.crypto.keys import (
    DEFAULT_FILESYSTEM_KEYSTORE_DIR,
    FilesystemKeystore,
    KeystoreBackend,
    Pkcs11Keystore,
    SecretManagerKeystore,
    load_keystore,
)


@pytest.fixture()
def keystore_dir(tmp_path: Path) -> Path:
    return tmp_path / "keys"


def test_filesystem_keystore_roundtrip(keystore_dir: Path) -> None:
    ks = FilesystemKeystore(directory=keystore_dir)
    ks.store_key("alpha", b"\x00" * 32, key_type="signing")
    ks.store_key("beta", b"\x01" * 32, key_type="encryption")

    assert sorted(ks.list_keys()) == ["alpha", "beta"]
    assert ks.load_key("alpha") == b"\x00" * 32
    assert ks.load_key("beta") == b"\x01" * 32

    ks.delete_key("alpha")
    assert ks.list_keys() == ["beta"]
    with pytest.raises(KeyError):
        ks.load_key("alpha")


def test_filesystem_keystore_key_file_is_0600(keystore_dir: Path) -> None:
    ks = FilesystemKeystore(directory=keystore_dir)
    ks.store_key("k", b"\xaa" * 32)
    key_path = keystore_dir / "k.key"
    mode = stat.S_IMODE(os.stat(key_path).st_mode)
    assert mode == 0o600


def test_filesystem_keystore_directory_is_0700(keystore_dir: Path) -> None:
    FilesystemKeystore(directory=keystore_dir)
    mode = stat.S_IMODE(os.stat(keystore_dir).st_mode)
    assert mode == 0o700


def test_filesystem_keystore_symlinked_directory_is_rejected(tmp_path: Path) -> None:
    decoy = tmp_path / "decoy"
    decoy.mkdir(mode=0o755)
    keystore_link = tmp_path / "keys"
    keystore_link.symlink_to(decoy)

    with pytest.raises(OSError):
        FilesystemKeystore(directory=keystore_link)

    assert stat.S_IMODE(os.stat(decoy).st_mode) == 0o755


def test_filesystem_keystore_directory_owned_by_other_user_is_rejected(
    keystore_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    keystore_dir.mkdir(parents=True)
    real_uid = os.getuid()
    monkeypatch.setattr(os, "getuid", lambda: real_uid + 1)

    with pytest.raises(PermissionError):
        FilesystemKeystore(directory=keystore_dir)


def test_filesystem_keystore_metadata_sidecar_shape(keystore_dir: Path) -> None:
    ks = FilesystemKeystore(directory=keystore_dir)
    ks.store_key("k", b"\xaa" * 32, key_type="signing")
    meta_path = keystore_dir / "k.meta.json"
    meta = json.loads(meta_path.read_text())
    assert "created_at" in meta
    assert meta["key_type"] == "signing"


def test_filesystem_keystore_delete_unknown_raises(keystore_dir: Path) -> None:
    ks = FilesystemKeystore(directory=keystore_dir)
    with pytest.raises(KeyError):
        ks.delete_key("nope")


class _FixedActionHooks:
    """Hooks impl that returns a configured RotationAction every call."""

    def __init__(self, action: RotationAction) -> None:
        self.action = action
        self.calls: list[tuple[KeyReference, timedelta, str]] = []

    def select_he_backend(self, operation, parties=()) -> HEBackendSpec:  # noqa: D401
        return HEBackendSpec(
            backend_name="x",
            scheme="CKKS",
            params=(),
            key_refs=(),
            threat_model="single_key",
        )

    def threshold_sign(self, message, signers, threshold) -> ThresholdSignature:
        raise NotImplementedError

    def verify_tee_attestation(self, instance, evidence, expected_measurements=()):
        raise NotImplementedError

    def enforce_key_rotation_policy(self, key_ref, key_age, operation) -> RotationAction:
        self.calls.append((key_ref, key_age, operation))
        return self.action


@pytest.mark.parametrize(
    "action",
    [RotationAction.ALLOW, RotationAction.WARN],
)
def test_filesystem_keystore_load_respects_allow_and_warn(
    keystore_dir: Path, action: RotationAction, caplog: pytest.LogCaptureFixture
) -> None:
    hooks = _FixedActionHooks(action)
    ks = FilesystemKeystore(directory=keystore_dir, hooks=hooks)
    ks.store_key("k", b"\xbb" * 32, key_type="signing")

    with caplog.at_level(logging.WARNING):
        out = ks.load_key("k")
    assert out == b"\xbb" * 32
    assert len(hooks.calls) == 1
    key_ref, _age, op = hooks.calls[0]
    assert key_ref.key_id == "k"
    assert key_ref.keystore == "filesystem"
    assert key_ref.key_type == "signing"
    assert op == "sign" or op == "use"


def test_filesystem_keystore_load_blocks(keystore_dir: Path) -> None:
    hooks = _FixedActionHooks(RotationAction.BLOCK)
    ks = FilesystemKeystore(directory=keystore_dir, hooks=hooks)
    ks.store_key("k", b"\xbb" * 32)
    with pytest.raises(PermissionError, match="BLOCK"):
        ks.load_key("k")


def test_filesystem_keystore_load_rotate_first(
    keystore_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    hooks = _FixedActionHooks(RotationAction.ROTATE_FIRST)
    ks = FilesystemKeystore(directory=keystore_dir, hooks=hooks)
    ks.store_key("k", b"\xbb" * 32)
    with caplog.at_level(logging.INFO, logger="backend.crypto.keys"):
        out = ks.load_key("k")
    assert out == b"\xbb" * 32
    assert any("Rotation stub fired" in r.message for r in caplog.records)


def test_filesystem_keystore_load_unknown_key_raises(keystore_dir: Path) -> None:
    ks = FilesystemKeystore(directory=keystore_dir)
    with pytest.raises(KeyError):
        ks.load_key("ghost")


def test_filesystem_keystore_load_with_missing_meta_uses_mtime(keystore_dir: Path) -> None:
    ks = FilesystemKeystore(directory=keystore_dir)
    ks.store_key("k", b"\xcc" * 32)
    # Remove the sidecar to force the fallback path.
    (keystore_dir / "k.meta.json").unlink()
    assert ks.load_key("k") == b"\xcc" * 32


def test_filesystem_keystore_default_hooks_is_null(keystore_dir: Path) -> None:
    ks = FilesystemKeystore(directory=keystore_dir)
    assert isinstance(ks.hooks, NullAISCryptoHooks)


def test_filesystem_keystore_directory_defaults_to_dotjackpot_keys() -> None:
    assert Path.home() / ".jackpot" / "keys" == DEFAULT_FILESYSTEM_KEYSTORE_DIR


def test_secret_manager_keystore_raises_with_deferral_message() -> None:
    ks = SecretManagerKeystore()
    with pytest.raises(NotImplementedError, match="GCP integration sprint"):
        ks.load_key("k")
    with pytest.raises(NotImplementedError, match="GCP integration sprint"):
        ks.store_key("k", b"\x00" * 32)
    with pytest.raises(NotImplementedError, match="GCP integration sprint"):
        ks.list_keys()
    with pytest.raises(NotImplementedError, match="GCP integration sprint"):
        ks.delete_key("k")


def test_pkcs11_keystore_raises_with_deferral_message() -> None:
    ks = Pkcs11Keystore()
    with pytest.raises(NotImplementedError, match="hardware-token sprint"):
        ks.load_key("k")
    with pytest.raises(NotImplementedError, match="hardware-token sprint"):
        ks.store_key("k", b"\x00" * 32)
    with pytest.raises(NotImplementedError, match="hardware-token sprint"):
        ks.list_keys()
    with pytest.raises(NotImplementedError, match="hardware-token sprint"):
        ks.delete_key("k")


def test_load_keystore_dispatches_on_name(keystore_dir: Path) -> None:
    fs = load_keystore("filesystem", directory=keystore_dir)
    assert isinstance(fs, FilesystemKeystore)

    sm = load_keystore("secret_manager")
    assert isinstance(sm, SecretManagerKeystore)

    pk = load_keystore("pkcs11")
    assert isinstance(pk, Pkcs11Keystore)

    with pytest.raises(ValueError, match="Unknown keystore backend"):
        load_keystore("unknown")


def test_keystore_backend_is_abstract() -> None:
    with pytest.raises(TypeError):
        KeystoreBackend()  # type: ignore[abstract]


def test_hooks_compatibility_via_protocol() -> None:
    hooks: AISCryptoHooks = _FixedActionHooks(RotationAction.ALLOW)
    assert isinstance(hooks, AISCryptoHooks)


@pytest.fixture
def no_chmod(monkeypatch: pytest.MonkeyPatch):
    """umask 0 and a neutered chmod, leaving only the mode at creation.

    Asserting the finished file is 0600 proves nothing: write-then-chmod
    ends at 0600 too, which is why every existing permission test here
    passed while the window was open. Taking chmod away is what separates
    "created private" from "made private afterwards".
    """
    previous = os.umask(0)
    monkeypatch.setattr(os, "chmod", lambda *args, **kwargs: None)
    monkeypatch.setattr(Path, "chmod", lambda self, mode: None)
    try:
        yield
    finally:
        os.umask(previous)


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission bits")
def test_filesystem_keystore_files_are_created_private_not_chmodded_private(
    keystore_dir: Path, no_chmod
) -> None:
    ks = FilesystemKeystore(directory=keystore_dir)
    ks.store_key("k", b"\xaa" * 32)

    # 0666 here means the bytes hit the disk world-readable and only a
    # later chmod saved them — the window this guards against.
    assert stat.S_IMODE(os.stat(keystore_dir / "k.key").st_mode) == 0o600
    assert stat.S_IMODE(os.stat(keystore_dir / "k.meta.json").st_mode) == 0o600
