# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Tests for backend.crypto.keys."""

from __future__ import annotations

import itertools
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
def no_chmod(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """umask 0 and a neutered chmod, leaving only the mode at creation.

    Asserting the finished file is 0600 proves nothing: write-then-chmod
    ends at 0600 too, which is why every existing permission test here
    passed while the window was open. Taking chmod away is what separates
    "created private" from "made private afterwards".
    """
    previous = os.umask(0)
    real_fchmod = os.fchmod

    def _fchmod_regular_files_only(fd: int, mode: int) -> None:
        # Directories still need it — FilesystemKeystore's _mkdir_and_secure
        # locks the keystore dir this way. Only the file route is closed,
        # otherwise an implementation could pass by tightening after
        # creation, which is the very thing under test.
        if stat.S_ISREG(os.fstat(fd).st_mode):
            return
        real_fchmod(fd, mode)

    monkeypatch.setattr(os, "chmod", lambda *args, **kwargs: None)
    monkeypatch.setattr(Path, "chmod", lambda self, mode: None)
    monkeypatch.setattr(os, "fchmod", _fchmod_regular_files_only)
    # Guard the guard (Rule 74). If either monkeypatch ever stops taking —
    # a module-scope `from os import chmod`, a helper reaching through
    # shutil — every assertion below goes green against defective code, and
    # green is indistinguishable from working.
    probe = tmp_path / ".chmod_canary"
    os.close(os.open(probe, os.O_WRONLY | os.O_CREAT, 0o644))
    os.chmod(probe, 0o600)
    probe.chmod(0o600)
    fd = os.open(probe, os.O_WRONLY)
    try:
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)
    assert stat.S_IMODE(os.stat(probe).st_mode) == 0o644, (
        "chmod or fchmod is still live — this fixture no longer isolates the creation mode"
    )
    try:
        yield
    finally:
        os.umask(previous)


def test_filesystem_keystore_metadata_sidecar_is_created_private(
    keystore_dir: Path, no_chmod
) -> None:
    ks = FilesystemKeystore(directory=keystore_dir)
    ks.store_key("k", b"\xaa" * 32)

    # The sidecar is the assertion with signal: it was the write_text() one,
    # so 0666 here means the bytes hit the disk world-readable and only a
    # later chmod saved them.
    assert stat.S_IMODE(os.stat(keystore_dir / "k.meta.json").st_mode) == 0o600
    # The key file cannot fail this line — it used os.open(..., 0o600) before
    # this branch and mkstemp after. Kept as the pair, not as the guard; the
    # key file's real coverage is the overwrite test below.
    assert stat.S_IMODE(os.stat(keystore_dir / "k.key").st_mode) == 0o600


def test_filesystem_keystore_narrows_a_preexisting_world_readable_file(
    keystore_dir: Path, no_chmod
) -> None:
    """os.open's mode argument only applies on creation.

    A key file already sitting at 0644 would, under an in-place rewrite, be
    truncated and rewritten at its existing mode — publishing the
    *replacement* key material. _write_0600 never writes through the live
    file: mkstemp creates a fresh 0600 one and os.replace swaps it in, so
    the old mode does not survive the write.
    """
    keystore_dir.mkdir(parents=True, exist_ok=True)
    stale = keystore_dir / "k.key"
    # 0644 via the creation mode — chmod is neutered by the fixture, and
    # umask is 0, so this lands exactly as asked.
    os.close(os.open(stale, os.O_WRONLY | os.O_CREAT, 0o644))
    assert stat.S_IMODE(os.stat(stale).st_mode) == 0o644

    ks = FilesystemKeystore(directory=keystore_dir)
    ks.store_key("k", b"\xbb" * 32)

    assert stat.S_IMODE(os.stat(stale).st_mode) == 0o600


# --- key_id must not be able to name a path outside the keystore -------------

TRAVERSING_KEY_IDS = [
    "../escaped",
    "../../etc/cron.d/evil",
    "sub/dir/key",
    "..",
    ".",
    "",
    ".hidden",  # collides with the mkstemp prefix, and hides the key
    "key\x00.png",  # NUL truncation in the syscall layer
    "a" * 300,  # ENAMETOOLONG rather than a clean refusal
    "key with space",
    "key;rm -rf /",
    "alpha\n",  # `$` matches before a final newline; fullmatch does not
]


@pytest.mark.parametrize("key_id", TRAVERSING_KEY_IDS)
def test_filesystem_keystore_refuses_key_ids_that_are_not_plain_names(
    keystore_dir: Path, key_id: str
) -> None:
    """Every method that turns a key_id into a path must refuse these.

    Checking store_key alone would leave the read side open: load_key and
    delete_key build their own paths, so each is asserted separately.
    """
    ks = FilesystemKeystore(directory=keystore_dir)

    with pytest.raises(ValueError):
        ks.store_key(key_id, b"\xaa" * 32)
    with pytest.raises(ValueError):
        ks.load_key(key_id)
    with pytest.raises(ValueError):
        ks.delete_key(key_id)


def test_filesystem_keystore_still_accepts_ordinary_key_ids(keystore_dir: Path) -> None:
    """The other direction — a validator that refuses everything is not a fix.

    Includes the one id the codebase actually uses today
    (settings.federation_signing_key_id defaults to "federation-signing").
    """
    ks = FilesystemKeystore(directory=keystore_dir)

    for key_id in ("federation-signing", "k", "peer_key.v2", "KEY-2026"):
        ks.store_key(key_id, b"\xaa" * 32)
        assert ks.load_key(key_id) == b"\xaa" * 32
        assert key_id in ks.list_keys()


def test_no_accepted_key_id_can_name_a_path_outside_the_keystore(keystore_dir: Path) -> None:
    """Directional property over generated input, not a hand-picked list.

    The list above came from the same head that wrote the regex, so it can
    only contain cases already thought of. This composes separators, dots and
    prefixes mechanically and asserts the one direction that matters: if the
    id is accepted, the path it builds resolves inside the keystore.
    """
    ks = FilesystemKeystore(directory=keystore_dir)
    root = keystore_dir.resolve()

    pieces = ["", ".", "..", "/", "\\", "a", "-", "_", "~", "%2e"]
    for a, b, c in itertools.product(pieces, repeat=3):
        key_id = a + b + c
        try:
            path = ks._key_path(key_id)
        except ValueError:
            continue  # refused — nothing to escape with
        assert path.resolve().parent == root, f"{key_id!r} escaped to {path}"
        assert path.name.endswith(".key")
