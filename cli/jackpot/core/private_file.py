# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Writing files that are never briefly readable by anyone else."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_private(path: Path, content: bytes | str, *, mode: int = 0o600) -> None:
    """Write ``content`` to ``path``, which never exists more open than ``mode``.

    ``path.write_text(...)`` followed by ``path.chmod(0o600)`` is the obvious
    shape and the wrong one: between those two calls the file exists under the
    process umask — 0644 on a typical machine — holding a token or a private
    key. A local reader only has to be looking at the right moment.

    So the bytes go to a ``mkstemp`` file in the same directory, which the OS
    creates 0600 before any content lands in it, and ``os.replace`` moves it
    into place. The replace is atomic and carries the temp file's mode with it,
    so an existing file at a wider mode is narrowed in the same step rather
    than after the fact. A process dying mid-write leaves the previous file
    rather than a truncated one — there is no fsync, so this says nothing
    about power loss, and durability is not what the helper is for.
    """
    data = content.encode() if isinstance(content, str) else content
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
