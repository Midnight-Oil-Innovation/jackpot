"""
Secret generation for `jackpot init secrets`.

Per Decision 5 in docs/architecture/jackpot-init-cli.md:

- JWT signing key: 32-byte hex string (256 bits) via `secrets.token_hex`.
  Generated for every scenario.
- ed25519 federation keypair: only for Scenarios E (federation member)
  and T (Tribal-sovereignty — uses local keypair regardless of broader
  network policy).
- OAuth client secret: prompted from operator for scenarios with
  `auth_method == "oauth"` or `"sso"`. Never generated; the operator
  obtains it from their OAuth provider's console.

Per Decision 7: re-running with existing secrets PRESERVES them by
default. `--regenerate-secrets` triggers per-secret confirmation
prompts before overwriting.

File output (instances/<name>/secrets/):
- `jwt_signing_key.txt`           — generated, 0600
- `federation_private_key.pem`    — generated for E/T, 0600
- `federation_public_key.pem`     — public counterpart, 0644 (committable)
- `oauth_client_secret.txt`       — operator-typed for OAuth/SSO, 0600
"""

from __future__ import annotations

import secrets as _stdlib_secrets
from dataclasses import dataclass
from pathlib import Path

from jackpot_scenarios.scenarios import Scenario
from nacl.encoding import RawEncoder
from nacl.signing import SigningKey

from jackpot.core.private_file import write_private
from jackpot.init.writers import is_secret_path


@dataclass(frozen=True)
class SecretWriteRecord:
    """One secret-file write outcome."""

    path: Path
    action: str  # "wrote_new" | "regenerated" | "preserved" | "skipped_not_applicable"


def generate_jwt_signing_key() -> str:
    """Cryptographically secure 32-byte hex string. Used by the backend
    JWT signer."""
    return _stdlib_secrets.token_hex(32)


def generate_ed25519_keypair() -> tuple[bytes, bytes]:
    """Generate an ed25519 keypair for federation message signing.

    Returns (private_key_pem, public_key_pem) — both as PEM-formatted
    bytes. The private key is wrapped with a permissive PEM header so
    operators can grep / hand-edit if needed; the format is informal
    (not standard PKCS#8) because federation peers consume the raw
    32-byte key, not the PEM envelope.
    """
    sk = SigningKey.generate()
    private_raw = sk.encode(encoder=RawEncoder)
    public_raw = sk.verify_key.encode(encoder=RawEncoder)

    private_pem = (
        b"-----BEGIN ED25519 PRIVATE KEY-----\n"
        + private_raw.hex().encode("ascii")
        + b"\n-----END ED25519 PRIVATE KEY-----\n"
    )
    public_pem = (
        b"-----BEGIN ED25519 PUBLIC KEY-----\n"
        + public_raw.hex().encode("ascii")
        + b"\n-----END ED25519 PUBLIC KEY-----\n"
    )
    return private_pem, public_pem


def _scenario_needs_federation_keypair(scenario: Scenario) -> bool:
    """Per Decision 5: Scenarios E (federation member) and T
    (Tribal-sovereignty — uses local keypair regardless of broader
    network policy) need federation keypairs at install time."""
    return scenario.code in {"E", "T"}


def _scenario_needs_oauth_secret(scenario: Scenario) -> bool:
    """Operator must paste the OAuth client secret for any scenario
    where the backend will speak real OAuth/SSO."""
    return scenario.defaults.auth_method in {"oauth", "sso"}


def write_secret_file(
    path: Path,
    content: bytes | str,
    *,
    regenerate: bool,
    confirm_overwrite,
    perms: int = 0o600,
) -> SecretWriteRecord:
    """Write `content` to `path` honouring the secret-preservation rule.

    `confirm_overwrite` is a callable `(path) -> bool` — invoked when
    `regenerate=True` AND the file already exists. The CLI plugs in a
    Click prompt; tests can pass `lambda _: True` / `lambda _: False`.
    """
    if not path.exists():
        write_private(path, content, mode=perms)
        return SecretWriteRecord(path=path, action="wrote_new")

    # File exists.
    if not regenerate:
        return SecretWriteRecord(path=path, action="preserved")

    # Regenerate requested — confirm first.
    if not confirm_overwrite(path):
        return SecretWriteRecord(path=path, action="preserved")

    write_private(path, content, mode=perms)
    return SecretWriteRecord(path=path, action="regenerated")


def populate_secrets(
    *,
    scenario: Scenario,
    instance_dir: Path,
    regenerate_secrets: bool,
    confirm_overwrite,
    oauth_secret_provider,
) -> list[SecretWriteRecord]:
    """Populate `instance_dir/secrets/` with the secrets the scenario needs.

    `oauth_secret_provider` is a callable `() -> str | None` — invoked
    when the scenario needs an OAuth client secret. Returns None when
    the operator declines to paste a value (e.g. they're configuring
    the operator-config separately and will write the file by hand).
    The CLI plugs in a Click prompt; tests pass deterministic stubs.
    """
    secrets_dir = instance_dir / "secrets"
    secrets_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    secrets_dir.chmod(0o700)  # narrow it too if it predates the mode= above

    records: list[SecretWriteRecord] = []

    # 1. JWT signing key — every scenario.
    records.append(
        write_secret_file(
            secrets_dir / "jwt_signing_key.txt",
            generate_jwt_signing_key() + "\n",
            regenerate=regenerate_secrets,
            confirm_overwrite=confirm_overwrite,
        )
    )

    # 2. Federation keypair — Scenarios E + T per Decision 5.
    if _scenario_needs_federation_keypair(scenario):
        # Public + private generated atomically; can't separately
        # regenerate one half. Caller's confirm_overwrite is invoked
        # for the private key only.
        private_key_path = secrets_dir / "federation_private_key.pem"
        public_key_path = secrets_dir / "federation_public_key.pem"

        if private_key_path.exists() and not regenerate_secrets:
            records.append(SecretWriteRecord(path=private_key_path, action="preserved"))
            records.append(SecretWriteRecord(path=public_key_path, action="preserved"))
        elif private_key_path.exists() and not confirm_overwrite(private_key_path):
            records.append(SecretWriteRecord(path=private_key_path, action="preserved"))
            records.append(SecretWriteRecord(path=public_key_path, action="preserved"))
        else:
            # Capture pre-write existence BEFORE writing, otherwise the
            # post-write `.exists()` is always True and every first-write
            # gets mislabeled as "regenerated".
            was_present = private_key_path.exists()
            private_pem, public_pem = generate_ed25519_keypair()
            write_private(private_key_path, private_pem)
            write_private(public_key_path, public_pem, mode=0o644)  # public — readable
            action = "regenerated" if was_present else "wrote_new"
            records.append(SecretWriteRecord(path=private_key_path, action=action))
            records.append(SecretWriteRecord(path=public_key_path, action=action))
    else:
        records.append(
            SecretWriteRecord(
                path=secrets_dir / "federation_private_key.pem",
                action="skipped_not_applicable",
            )
        )

    # 3. OAuth client secret — scenarios with real auth.
    if _scenario_needs_oauth_secret(scenario):
        secret_path = secrets_dir / "oauth_client_secret.txt"
        if secret_path.exists() and not regenerate_secrets:
            records.append(SecretWriteRecord(path=secret_path, action="preserved"))
        else:
            value = oauth_secret_provider()
            if value is None or not value.strip():
                records.append(SecretWriteRecord(path=secret_path, action="skipped_not_applicable"))
            else:
                records.append(
                    write_secret_file(
                        secret_path,
                        value.strip() + "\n",
                        regenerate=regenerate_secrets,
                        confirm_overwrite=confirm_overwrite,
                    )
                )
    else:
        records.append(
            SecretWriteRecord(
                path=instance_dir / "secrets" / "oauth_client_secret.txt",
                action="skipped_not_applicable",
            )
        )

    return records


# Sanity-check: the secrets module ONLY writes inside instances/<name>/
# directories that pass the `is_secret_path` test. If any future code
# starts writing secrets elsewhere, this property catches it.
def assert_secret_path_invariant(records: list[SecretWriteRecord]) -> None:
    """Raises AssertionError if any record's path isn't a secret path."""
    for rec in records:
        if rec.action == "skipped_not_applicable":
            continue
        if not is_secret_path(rec.path):
            raise AssertionError(f"Secret-handling code wrote to non-secret path: {rec.path}")


__all__ = [
    "SecretWriteRecord",
    "assert_secret_path_invariant",
    "generate_ed25519_keypair",
    "generate_jwt_signing_key",
    "populate_secrets",
    "write_secret_file",
]
