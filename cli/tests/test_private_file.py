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

import pytest

from jackpot.core.private_file import write_private


@pytest.fixture
def permissive_umask():
    """Run with umask 0 — write-then-chmod would leave 0666/0644 here."""
    previous = os.umask(0)
    try:
        yield
    finally:
        os.umask(previous)


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission bits")
def test_new_file_is_0600_under_a_permissive_umask(tmp_path, permissive_umask):
    target = tmp_path / "token.toml"

    write_private(target, "token = 'jk_secret'")

    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert target.read_text() == "token = 'jk_secret'"


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission bits")
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
