# `backend/crypto/` — Crypto Package

**Owner:** core platform
**Status:** Track 1 functional (filesystem keystore + Ed25519 single-signer); Track 2 hooks scaffolded.

## The two-track plan

JACKPOT cryptography ships with a working Track 1 surface (filesystem-backed keystore + Ed25519 signing) and a Track 2 `Protocol` seam (`AISCryptoHooks`) where AIS-flavored augmentation — HE backend selection, threshold signing, TEE attestation, key-rotation policy — slots in later. No separate "research" branch, no "v2 someday" hand-wave; Track 2 is structured stubs that ship next to the working code so when crypto/AIS collaborators land, they have a place to plug in.

This package is the third sibling of the scaffold trio:

- `backend/federation/` — FED-A (federation Protocol seam + Track 1 implementations)
- `backend/privacy/` — PRV-A (privacy Protocol seam + Track 1 wrappers)
- `backend/crypto/` — CRY-A (this package)

| Track | What it is | Where it lives in this package | Status |
|---|---|---|---|
| **Track 1 — Build** | Filesystem keystore (0600 perms + metadata sidecar + rotation-hook integration). Ed25519 single-signer using `cryptography` hazmat primitives. | `keys.py`, `signing.py` | Functional, tested |
| **Track 2 — Scaffold for AIS** | `AISCryptoHooks` Protocol — HE backend selection, threshold signing, TEE attestation verification, key-rotation policy. Stubs for Secret Manager / PKCS#11 keystores and GA4GH Crypt4GH. | `_ais_hooks.py`, `crypt4gh.py`, stub backends in `keys.py`, `signing.threshold_sign` | Hook surface defined; concrete impls deferred |

## Track 2 — `AISCryptoHooks` hook surface

Four hooks, one per operator decision point. Each maps to a specific AIS doc section and to the Track 2 implementation site at `backend/backend/immune/sec/crypto_backends.py`.

| Hook | AIS doc ref | Called by | Track 2 destination | Null behaviour |
|---|---|---|---|---|
| `select_he_backend(operation, parties)` | §1.4 adaptive immunity (state-bearing computation) | PRV-A `he_compute` Track 2 | `backend/backend/immune/sec/crypto_backends.py` | Sensible default — single-key TenSEAL CKKS, 8192 polynomial modulus degree |
| `threshold_sign(message, signers, threshold)` | §1.8 tolerance / regulation | FED-A `threshold_approve` Track 2 | `backend/backend/immune/sec/crypto_backends.py` (FROST / BLS-threshold) | Refuse — `NotImplementedError` (no silent degradation to single-signer) |
| `verify_tee_attestation(instance, evidence, expected_measurements)` | §1.7 attribution & deception | FED-A `attest_partner` Track 2 | `backend/backend/immune/sec/crypto_backends.py` (SEV-SNP / TDX / TPM-2.0) | Refuse — `AttestationResult(verified=False, reason="No Track 2 …")` |
| `enforce_key_rotation_policy(key_ref, key_age, operation)` | §1.8 tolerance / regulation | `backend/crypto/keys.FilesystemKeystore.load_key` | `backend/backend/immune/sec/crypto_backends.py` (operator policy engine) | Permissive — `RotationAction.ALLOW` |

`NullAISCryptoHooks` is the Track 1 default everywhere. Operators wire a Track 2 implementation in via constructor DI on the relevant Track 1 class:

```python
from backend.crypto import FilesystemKeystore
from backend.immune.sec.crypto_backends import RealAISCryptoHooks  # Track 2

# Track 1 deployment (default):
ks = FilesystemKeystore()  # uses NullAISCryptoHooks, permissive rotation

# Track 2 deployment:
ks = FilesystemKeystore(hooks=RealAISCryptoHooks(...))  # operator policy enforced
```

## Track 1 — what works today

### `keys.py` — keystore abstraction

- `KeystoreBackend` ABC — `load_key` / `store_key` / `list_keys` / `delete_key`.
- `FilesystemKeystore` — fully functional. Stores keys at `<dir>/<key_id>.key` (0600) with a `<dir>/<key_id>.meta.json` sidecar (`created_at`, `key_type`). Default directory `~/.jackpot/keys/`. The load path consults the configured `AISCryptoHooks.enforce_key_rotation_policy` hook and respects `ALLOW` / `WARN` / `ROTATE_FIRST` / `BLOCK` actions.
- `SecretManagerKeystore` — stubbed. Raises `NotImplementedError("Secret Manager keystore deferred to Track 2 / GCP integration sprint.")`
- `Pkcs11Keystore` — stubbed. Raises `NotImplementedError("PKCS#11 keystore deferred to Track 2 / hardware-token sprint.")`
- `load_keystore(name, **kwargs)` — factory dispatching on backend name.

### `signing.py` — signing primitives

- `Ed25519Signer` — fully functional. Loads a 32-byte Ed25519 seed from any `KeystoreBackend`, exposes `sign(message)` / `verify(message, signature, public_key)` / `public_key_bytes()`. Uses `cryptography.hazmat.primitives.asymmetric.ed25519` directly — no third-party signing library.
- `threshold_sign(message, signers, threshold, hooks=None)` — top-level delegate to the configured `AISCryptoHooks.threshold_sign` hook. Default `NullAISCryptoHooks` raises; Track 2 supplies real FROST / BLS-threshold.

## Track 2 — what's stubbed

- `SecretManagerKeystore` and `Pkcs11Keystore` raise `NotImplementedError` with explicit deferral notes.
- `Crypt4ghEncryptor` in `crypt4gh.py` raises `NotImplementedError` referencing `B-CRY-CRYPT4GH-1`. Real GA4GH Crypt4GH integration lands in the sequence-archive sprint.
- `threshold_sign`, `verify_tee_attestation`, and any HE-backend tuning beyond the conservative default await the Track 2 crypto-backends module.

## Mapping to existing roadmap items

| Source | Item | Lives in |
|---|---|---|
| `todo.md` Federation/Privacy/Crypto Scaffolds | CRY-A | This package |
| `todo.md` cryptWWDB Integration Track | `B-CRY-CRYPT4GH-1` (new follow-up) | `crypt4gh.py` deferral note |
| `Jackpot_AIS.md` §1.4 adaptive immunity | HE backend selection | `_ais_hooks.AISCryptoHooks.select_he_backend` |
| `Jackpot_AIS.md` §1.7 attribution & deception | TEE attestation | `_ais_hooks.AISCryptoHooks.verify_tee_attestation` |
| `Jackpot_AIS.md` §1.8 tolerance / regulation | Threshold sign + rotation policy | `_ais_hooks.AISCryptoHooks.threshold_sign`, `enforce_key_rotation_policy` |
| `jackpot_immune_platform_plan.md` §6.2.2, §10.5 | HE & TEE backend selection per Driver et al. 2024 | Track 2 destination |
| `docs/federation_operations.md` §2 | Three-party non-collusion assumption | Threat model note (below) |
| `B-CRY-1` (security backlog) | Encryption hardening (Crypt4GH ingest, threshold-signed governance, TEE attestation) | Concrete impl at `backend/backend/immune/sec/crypto_backends.py` |

## Relationship to `backend/immune/`

This package is **Track 1** — cryptographic primitives that ship now using the `cryptography` library and the local filesystem. `backend/immune/` is **Track 2** — the AIS-augmented overlays scheduled per the immune-collaboration scaffolding plan.

The seam between the two tracks is the `AISCryptoHooks` Protocol defined in `_ais_hooks.py`. Track 1 ships with `NullAISCryptoHooks` (safe defaults + refuse-by-default where no safe default exists). Track 2 work delivers concrete hook implementations at `backend/backend/immune/sec/crypto_backends.py`, importing from sibling immune-scaffold modules. **No changes required to `keys.py` / `signing.py` / `crypt4gh.py`.** Direction of dependency is one-way: `backend/crypto/` never imports from `backend/immune/`; `backend/immune/sec/crypto_backends.py` imports the Protocol from `backend/crypto/_ais_hooks.py`.

## Threat model

This scaffold operates under the **three-party non-collusion assumption** documented in `docs/federation_operations.md` §2. The Track 1 surface (filesystem keystore, Ed25519 single-signer) is appropriate for single-instance operation and for the M-of-N threshold-cryptography work scheduled in Track 2 — provided that the three federation roles (sample originator, computation party, key-management party) are operated by independent organizations and do not collude. Single-instance deployments that violate the non-collusion assumption MUST configure a Track 2 `AISCryptoHooks` implementation that BLOCKs the relevant operations via `enforce_key_rotation_policy` and refuses HE-backend selection for cross-instance work.

## Tests

`tests/crypto/` mirrors this layout:

- `test_ais_hooks.py` — `NullAISCryptoHooks` satisfies the `AISCryptoHooks` Protocol; per-hook behavior (sensible default / refuse / ALLOW) verified; dataclass round-trips (frozen + hashable).
- `test_keys.py` — `FilesystemKeystore` round-trip (store + load + list + delete), 0600 file permissions, metadata sidecar shape, rotation-hook integration for each `RotationAction`, stub backends raise the expected `NotImplementedError`, `load_keystore` factory dispatch.
- `test_signing.py` — `Ed25519Signer` happy-path sign / verify; verify fails on tampered message; `threshold_sign` with `NullAISCryptoHooks` raises, with a stub hooks impl returns the expected `ThresholdSignature`.
- `test_crypt4gh.py` — `Crypt4ghEncryptor` methods raise `NotImplementedError` with the expected `B-CRY-CRYPT4GH-1` reference.

`NullAISCryptoHooks` is the test fixture for Track 1 behavior; stub hook impls in the tests stand in for Track 2 wiring.
