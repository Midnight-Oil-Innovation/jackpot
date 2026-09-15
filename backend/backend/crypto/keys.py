"""Keystore abstraction.

Three backends in this module:
  - FilesystemKeystore: fully functional Track 1 keystore. Stores key bytes
    at 0600 with a JSON metadata sidecar (created_at, key_type).
  - SecretManagerKeystore: stub. Track 2 / GCP integration sprint.
  - Pkcs11Keystore: stub. Track 2 / hardware-token sprint.

The FilesystemKeystore load path consults the configured AISCryptoHooks
enforce_key_rotation_policy hook before returning a key, so operators can
plug a rotation-policy engine in via DI without changing call sites.
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
import tempfile
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path

from backend.crypto._ais_hooks import (
    AISCryptoHooks,
    KeyReference,
    NullAISCryptoHooks,
    RotationAction,
)

logger = logging.getLogger(__name__)

DEFAULT_FILESYSTEM_KEYSTORE_DIR = Path.home() / ".jackpot" / "keys"


def _mkdir_and_secure(path: Path) -> None:
    """Create ``path`` (and parents) then lock it to owner-only (0700).

    ``mkdir()`` followed by a separate ``os.chmod(path, ...)`` is a TOCTOU
    race: ``chmod`` follows symlinks, so an attacker who pre-plants a
    symlink at ``path`` before this first runs can redirect the chmod to
    an arbitrary directory. Opening with ``O_NOFOLLOW`` and chmod-ing the
    resulting file descriptor closes that race. Also refuses to adopt a
    pre-existing REAL directory owned by another user, since a local
    attacker pre-creating the real directory at this path could otherwise
    have their directory silently "secured" and used to store this
    process's signing/encryption key material.
    """
    path.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        if st.st_uid != os.getuid():
            raise PermissionError(
                f"{path} exists and is owned by uid {st.st_uid}, not this "
                f"process's uid {os.getuid()}; refusing to adopt it."
            )
        os.fchmod(fd, stat.S_IRWXU)
    finally:
        os.close(fd)


# A key_id becomes a filename. Anything that is not a plain name can leave the
# keystore directory: `../x` climbs out, `sub/x` descends, a leading dot both
# hides the key and collides with the `.<name>.` prefix _write_0600's mkstemp
# uses. Start on alphanumeric and stay in that set — no separator of any kind
# survives it, so there is nothing left to normalise or resolve afterwards.
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# ponytail: case-sensitivity is the filesystem's, not ours. On APFS/NTFS
# "Alpha" and "alpha" are two key_ids and one file, so store_key("alpha")
# overwrites the key stored as "Alpha" — verified on macOS. Harmless while the
# only caller is trusted operator config; it becomes a key-substitution
# primitive the day a key_id arrives from a peer. Narrowing to [a-z0-9] would
# close it and would reject ids like "KEY-2026"; revisit together.

# Two of these plus ".meta.json" must fit a 255-byte filename.
_KEY_ID_MAX_LENGTH = 200


def _read_nofollow(path: Path) -> bytes:
    """Read ``path``, refusing to follow a symlink at the final component.

    _checked_key_id guarantees the key_id names a file *inside* the keystore.
    It cannot guarantee the file *is* inside it: a symlink planted at
    ``<dir>/alpha.key`` reads through to anywhere. The directory is 0700 and
    ownership-checked, so this is not a boundary today — but _mkdir_and_secure
    went to O_NOFOLLOW lengths against exactly this shape, and the write side
    is already safe because os.replace swaps over a link rather than through
    it. Leaving only the read path following links is the kind of asymmetry
    that reads as deliberate later.
    """
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        return handle.read()


def _checked_key_id(key_id: str) -> str:
    """Return ``key_id`` if it can only ever name a file inside the keystore.

    Raises ValueError otherwise. Every path-building method routes through
    here rather than each validating for itself: the read and delete sides
    construct their own paths, so guarding only ``store_key`` would leave
    ``load_key`` able to read whatever the caller named.

    Today the sole caller is ``settings.federation_signing_key_id``, which is
    operator config and therefore trusted — this is not closing a live hole.
    It is closing the one that opens the first time a key_id arrives from a
    federation peer or an admin endpoint, which is a change nobody would think
    to review as a path-traversal question.
    """
    if not isinstance(key_id, str):
        raise ValueError(f"key_id must be a string, got {type(key_id).__name__}")
    if len(key_id) > _KEY_ID_MAX_LENGTH:
        raise ValueError(f"key_id is {len(key_id)} characters; the limit is {_KEY_ID_MAX_LENGTH}")
    # fullmatch, not match: `$` also matches before a final newline, so
    # `match` accepts "alpha\n" and writes a filename with a newline in it.
    if not _KEY_ID_RE.fullmatch(key_id):
        raise ValueError(
            f"key_id {key_id!r} is not a plain name: it must start with a letter or "
            "digit and contain only letters, digits, dot, underscore and hyphen."
        )
    return key_id


def _write_0600(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path``, which never exists more open than 0600.

    Same shape as ``jackpot.core.private_file.write_private`` in the CLI
    package, deliberately: two answers to "write a file nobody else can
    read" is one too many, and the packages cannot import each other.

    ``write_text()`` then ``chmod()`` leaves the file at the process umask —
    0644 on a typical machine — for the moment in between. Nor is the mode
    argument to ``os.open`` enough on its own: it applies only on creation,
    so an existing 0644 key is truncated and rewritten at 0644, exposing the
    *replacement* key.

    ``mkstemp`` sidesteps both. The OS creates it 0600 before any byte
    lands, and ``os.replace`` swaps it into place atomically — over a
    symlink rather than through it, and without ever truncating the live
    file. That last part matters here more than it does in the CLI:
    ``load_key`` ends at ``read_bytes()`` with no length check, so a crash
    or ENOSPC partway through an in-place rewrite would leave a short key
    that loads silently.
    """
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class KeystoreBackend(ABC):
    """Common interface across filesystem / Secret Manager / PKCS#11 backends."""

    @abstractmethod
    def load_key(self, key_id: str) -> bytes: ...

    @abstractmethod
    def store_key(self, key_id: str, key_bytes: bytes, *, key_type: str = "signing") -> None: ...

    @abstractmethod
    def list_keys(self) -> list[str]: ...

    @abstractmethod
    def delete_key(self, key_id: str) -> None: ...


class FilesystemKeystore(KeystoreBackend):
    """Track 1 filesystem-backed keystore.

    Stores each key as `<dir>/<key_id>.key` (0600) with a sibling
    `<dir>/<key_id>.meta.json` holding {created_at, key_type}. The load path
    invokes the configured AISCryptoHooks rotation-policy hook; ROTATE_FIRST
    triggers an in-place rotation stub (logs and returns the current key for
    now — Track 2 will replace with real rotation).
    """

    def __init__(
        self,
        directory: Path | None = None,
        *,
        hooks: AISCryptoHooks | None = None,
    ) -> None:
        self.directory = (
            Path(directory) if directory is not None else DEFAULT_FILESYSTEM_KEYSTORE_DIR
        )
        # Tighten directory perms (0700) so siblings can't list keys.
        _mkdir_and_secure(self.directory)
        self.hooks: AISCryptoHooks = hooks if hooks is not None else NullAISCryptoHooks()

    def _key_path(self, key_id: str) -> Path:
        return self.directory / f"{_checked_key_id(key_id)}.key"

    def _meta_path(self, key_id: str) -> Path:
        return self.directory / f"{_checked_key_id(key_id)}.meta.json"

    def store_key(self, key_id: str, key_bytes: bytes, *, key_type: str = "signing") -> None:
        key_path = self._key_path(key_id)
        meta_path = self._meta_path(key_id)
        _write_0600(key_path, key_bytes)
        meta = {
            "created_at": datetime.now(UTC).isoformat(),
            "key_type": key_type,
        }
        _write_0600(meta_path, json.dumps(meta).encode())

    def load_key(self, key_id: str, *, operation: str = "use") -> bytes:
        key_path = self._key_path(key_id)
        if not key_path.exists():
            raise KeyError(f"Key not found: {key_id}")
        meta = self._load_meta(key_id)
        key_ref = KeyReference(
            key_id=key_id,
            key_type=meta.get("key_type", "unknown"),
            keystore="filesystem",
            created_at=_parse_iso(meta["created_at"]),
        )
        key_age = datetime.now(UTC) - key_ref.created_at
        action = self.hooks.enforce_key_rotation_policy(key_ref, key_age, operation)

        if action == RotationAction.BLOCK:
            raise PermissionError(
                f"Key rotation policy BLOCKed use of {key_id} (age={key_age}, op={operation})"
            )
        if action == RotationAction.ROTATE_FIRST:
            logger.warning(
                "Rotation policy requires rotate-first for %s (age=%s); rotating in place",
                key_id,
                key_age,
            )
            self._rotate_in_place(key_id)
        elif action == RotationAction.WARN:
            logger.warning(
                "Rotation policy WARN for %s (age=%s, op=%s)", key_id, key_age, operation
            )
        # ALLOW falls through

        return _read_nofollow(key_path)

    def list_keys(self) -> list[str]:
        # Filter through the same predicate load_key applies, so everything
        # listed can actually be loaded. A stray `.hidden.key` in the directory
        # otherwise yields an id that this class's own load_key rejects.
        return sorted(p.stem for p in self.directory.glob("*.key") if _KEY_ID_RE.fullmatch(p.stem))

    def delete_key(self, key_id: str) -> None:
        key_path = self._key_path(key_id)
        meta_path = self._meta_path(key_id)
        if not key_path.exists():
            raise KeyError(f"Key not found: {key_id}")
        key_path.unlink()
        if meta_path.exists():
            meta_path.unlink()

    def _load_meta(self, key_id: str) -> dict[str, str]:
        meta_path = self._meta_path(key_id)
        if not meta_path.exists():
            # Missing sidecar — synthesize from filesystem mtime so the
            # rotation hook still has an age to evaluate against.
            mtime = datetime.fromtimestamp(self._key_path(key_id).stat().st_mtime, tz=UTC)
            return {"created_at": mtime.isoformat(), "key_type": "unknown"}
        return json.loads(meta_path.read_text())

    def _rotate_in_place(self, key_id: str) -> None:
        # Stub: real rotation requires Track 2 to generate a new key of the
        # right type and re-write the metadata. For now the hook is informed
        # but the key bytes are not regenerated.
        logger.info("Rotation stub fired for %s (Track 2 will replace this)", key_id)


class _StubKeystore(KeystoreBackend):
    """Shared base for stubbed keystore backends.

    Subclasses set `_unsupported_reason` to the message that should appear
    in NotImplementedError. All four abstract methods raise.
    """

    _unsupported_reason: str = "Stub keystore — Track 2 work required."

    def load_key(self, key_id: str) -> bytes:  # type: ignore[override]
        raise NotImplementedError(self._unsupported_reason)

    def store_key(self, key_id: str, key_bytes: bytes, *, key_type: str = "signing") -> None:
        raise NotImplementedError(self._unsupported_reason)

    def list_keys(self) -> list[str]:
        raise NotImplementedError(self._unsupported_reason)

    def delete_key(self, key_id: str) -> None:
        raise NotImplementedError(self._unsupported_reason)


class SecretManagerKeystore(_StubKeystore):
    """GCP Secret Manager keystore — stubbed.

    Tracked as Track 2 / GCP integration sprint. The interface matches
    KeystoreBackend so callers can swap implementations once the GCP wiring
    lands.
    """

    _unsupported_reason = "Secret Manager keystore deferred to Track 2 / GCP integration sprint."


class Pkcs11Keystore(_StubKeystore):
    """PKCS#11 hardware-token keystore — stubbed.

    Tracked as Track 2 / hardware-token sprint. The interface matches
    KeystoreBackend so callers can swap implementations once HSM / Yubikey
    integration lands.
    """

    _unsupported_reason = "PKCS#11 keystore deferred to Track 2 / hardware-token sprint."


def load_keystore(name: str, **kwargs: object) -> KeystoreBackend:
    """Factory: dispatch on backend name.

    Supported names: 'filesystem', 'secret_manager', 'pkcs11'. Extra kwargs
    are forwarded to the backend constructor (e.g. directory= for filesystem).
    """
    if name == "filesystem":
        return FilesystemKeystore(**kwargs)  # type: ignore[arg-type]
    if name == "secret_manager":
        return SecretManagerKeystore()
    if name == "pkcs11":
        return Pkcs11Keystore()
    raise ValueError(f"Unknown keystore backend: {name!r}")


def _parse_iso(value: str) -> datetime:
    # datetime.fromisoformat handles tz-aware ISO strings on 3.11+.
    return datetime.fromisoformat(value)


__all__ = [
    "DEFAULT_FILESYSTEM_KEYSTORE_DIR",
    "FilesystemKeystore",
    "KeystoreBackend",
    "Pkcs11Keystore",
    "SecretManagerKeystore",
    "load_keystore",
]
