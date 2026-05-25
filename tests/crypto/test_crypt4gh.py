# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Tests for backend.crypto.crypt4gh stub."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.crypto.crypt4gh import Crypt4ghEncryptor


def test_encrypt_file_raises_with_deferral_reference(tmp_path: Path) -> None:
    enc = Crypt4ghEncryptor()
    with pytest.raises(NotImplementedError, match="B-CRY-CRYPT4GH-1"):
        enc.encrypt_file(tmp_path / "in", tmp_path / "out", recipient_public_keys=(b"\x00",))


def test_decrypt_file_raises_with_deferral_reference(tmp_path: Path) -> None:
    enc = Crypt4ghEncryptor()
    with pytest.raises(NotImplementedError, match="B-CRY-CRYPT4GH-1"):
        enc.decrypt_file(tmp_path / "in", tmp_path / "out", recipient_private_key=b"\x00")


def test_deferral_reason_mentions_sequence_archive_sprint() -> None:
    enc = Crypt4ghEncryptor()
    with pytest.raises(NotImplementedError, match="sequence-archive sprint"):
        enc.encrypt_file(Path("/tmp/x"), Path("/tmp/y"), recipient_public_keys=())
