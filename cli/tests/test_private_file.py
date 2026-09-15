# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""``write_private`` must not depend on the caller's umask.

The defect it exists to prevent is a window, not an end state: write-then-chmod
ends at 0600 too. These tests pin the properties that distinguish the two —
the file is never created under the umask, and an existing wider file is
narrowed by the same operation that writes it.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from jackpot.core.private_file import write_private


@pytest.fixture
def permissive_umask():
    """Run with umask 0, so nothing masks a too-open creation mode."""
    previous = os.umask(0)
    try:
        yield
    finally:
        os.umask(previous)


@pytest.fixture
def no_chmod(permissive_umask, monkeypatch, tmp_path):
    """Take chmod away, leaving only the mode the file was created with.

    Asserting the finished file is 0600 proves nothing — write-then-chmod
    ends at 0600 too. That is exactly why the pre-existing call-site tests
    passed for as long as the window was open. Neutering chmod is what
    separates "created private" from "made private afterwards", and it is
    the only assertion here that fails if write_private is reverted.
    """
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


def test_new_file_is_created_0600_without_relying_on_chmod(tmp_path, no_chmod):
    target = tmp_path / "token.toml"

    write_private(target, "token = 'jk_secret'")

    # 0666 here would mean the token hit the disk world-readable and only a
    # later chmod saved it — the window this helper exists to close.
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert target.read_text() == "token = 'jk_secret'"


def test_existing_world_readable_file_is_narrowed(tmp_path, permissive_umask):
    target = tmp_path / "key.pem"
    target.write_text("old")
    target.chmod(0o644)

    write_private(target, b"new")

    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert target.read_bytes() == b"new"


def test_explicit_mode_is_honoured(tmp_path, permissive_umask):
    target = tmp_path / "public.pem"

    write_private(target, b"-----BEGIN PUBLIC KEY-----", mode=0o644)

    assert stat.S_IMODE(target.stat().st_mode) == 0o644


def test_missing_parent_directories_are_created(tmp_path):
    target = tmp_path / "nested" / "deeper" / "secret"

    write_private(target, "x")

    assert target.read_text() == "x"


def test_failed_write_leaves_no_temp_file_behind(tmp_path):
    target = tmp_path / "secret"

    with pytest.raises(TypeError):
        write_private(target, object())  # type: ignore[arg-type]

    assert not target.exists()
    assert list(tmp_path.iterdir()) == []
