> **Status:** Reference — operator/developer reference for the credential abstraction (Phase C-1).

# Credentials API Reference

This document is the operator and developer reference for the JACKPOT
credential abstraction (Phase C-1). It is **not** an HTTP endpoint
reference — credentials are not exposed over HTTP. It documents the
configuration patterns that make `backend.credentials.credentials.get(...)`
return a value for each of the supported backends, plus the
per-provider setup steps that each consuming feature (Globus, NCBI,
ENA, GISAID, federation, JWT) needs.

For the design rationale see the **Phase C-1 Specification** section
in [`spec.md`](../../spec.md). Critical Rule 62 in
[`docs/CLAUDE.md`](../CLAUDE.md) sets the call-site contract.

## Backends — selector and shape

`backend/config.py` exposes the selector and per-backend tunables:

| Setting | Default | Backend(s) it affects |
|---|---|---|
| `credential_backend` | `"env"` | All |
| `credential_file_path` | `~/.config/jackpot/credentials.yaml` | `file` |
| `credential_gcp_secret_prefix` | `"jackpot-cred-"` | `gcp_secret_manager` |
| `credential_cache_ttl_seconds` | `300` | All (facade-level cache) |

Pick a backend by setting `JACKPOT_CREDENTIAL_BACKEND` (or
`credential_backend` in operator config). The chosen backend is
constructed once per process via
`backend/credentials/factory.py::CredentialFactory`.

### Backend `env`

Reads `os.environ.get(<KEY>)` for each credential lookup.

**Setup:**

- Set the env var via `.env.local` (Compose), `values.local.yaml`
  (Helm), shell export, or operator's secret-management tool.
- Names are lowercase in the registry (`ncbi_api_key`,
  `globus_client_secret`, etc.); when reading via `os.environ` the
  backend uppercases (`NCBI_API_KEY`, `GLOBUS_CLIENT_SECRET`). Use
  the uppercase form when configuring env vars.

**Pros:** zero new infrastructure, works in every scenario, no file
permissions to manage.

**Cons:** plaintext on disk in `.env.local` files; not auditable
beyond OS-level audit logs; rotation is a process restart.

**Best for:** Scenarios A (laptop), F (CI), and B (small single-org
cloud) deployments. Default for new operators.

### Backend `file`

Reads a YAML file at `credential_file_path` whose top-level keys are
credential names (lowercase, matching the registry).

**Setup:**

```yaml
# ~/.config/jackpot/credentials.yaml — file mode MUST be 0600
ncbi_submission_username: jackpot-operator@example.org
ncbi_submission_password: "..."
ena_webin_username: Webin-12345
ena_webin_password: "..."
globus_client_id: "..."
globus_client_secret: "..."
jwt_secret_key: "..."
```

The backend refuses to read files with mode other than 0600 — so set
permissions before first start:

```bash
chmod 600 ~/.config/jackpot/credentials.yaml
```

**Pros:** config-management-friendly (Ansible / Chef / Puppet can drop
the file in place); single source of truth per host; easy to inspect.

**Cons:** still plaintext on disk; relies on filesystem permissions
for confidentiality.

**Best for:** Scenarios B (single-org cloud) and C (multi-lab agency)
deployments where operators already manage host-level secrets.

### Backend `gcp_secret_manager`

Fetches each credential from GCP Secret Manager with secret name
`<credential_gcp_secret_prefix><lowercase-key>` (default prefix
`jackpot-cred-`).

**Setup:**

1. Enable the API in your GCP project:
   ```bash
   gcloud services enable secretmanager.googleapis.com
   ```
2. Create one secret per credential:
   ```bash
   echo -n "..." | gcloud secrets create jackpot-cred-ncbi-submission-username \
       --replication-policy=automatic --data-file=-
   ```
3. Grant the JACKPOT runtime service account
   `roles/secretmanager.secretAccessor` on those secrets:
   ```bash
   gcloud secrets add-iam-policy-binding jackpot-cred-ncbi-submission-username \
       --member="serviceAccount:jackpot-api@<project>.iam.gserviceaccount.com" \
       --role="roles/secretmanager.secretAccessor"
   ```
4. Set `JACKPOT_CREDENTIAL_BACKEND=gcp_secret_manager` in the deployed
   pod's environment.

**Pros:** IAM-gated access; native rotation via secret versioning;
audit log automatically populated.

**Cons:** GCP-only; requires the `google-cloud-secret-manager` library
(already in the dependency tree for Scenarios D and E).

**Best for:** Scenarios D (hosted SaaS) and E (federation member)
deployments running on GCP.

## Required-credential registry

`backend/credentials/registry.py::REQUIRED_CREDENTIALS` is the
authoritative list of every credential JACKPOT may need. Each entry
includes:

```python
CredentialSpec(
    key="ncbi_api_key",
    required_predicate=lambda s: s.allow_backend_submission and "NCBI" in s.backend_submission_repos,
    description="NCBI API key for backend submission via Seqsender (I-3a).",
    example="abcdef1234567890",
)
```

`required_predicate` is a `Settings`-typed callable. The startup
validator (`facade.validate_required()`, called from `main.py`'s
lifespan handler) walks the registry, evaluates each predicate against
the live settings, and raises `RuntimeError` if any required
credential is unreachable. Fail-fast at boot beats discovering it on
first request.

## Per-provider setup

### JWT signing key

| Key | Required | Notes |
|---|---|---|
| `jwt_secret_key` | always | Used by `auth/oauth.py` and `auth/guards.py`. Rotate every 90 days; rotation invalidates all outstanding access tokens (refresh tokens via P1 still rotate cleanly). |

Default value `"dev-secret-key-change-in-prod"` is rejected when
`ENV=gcp` (Settings.validate_for_production checks).

### Globus

| Key | Required | Notes |
|---|---|---|
| `globus_client_id` | when `globus_enabled=true` | Globus OAuth client ID. |
| `globus_client_secret` | when `globus_enabled=true` | Paired secret. |
| `globus_endpoint_id` | when `globus_enabled=true` | UUID of the JACKPOT-managed Globus collection. |

Set up via Globus's developer console; provision the endpoint via the
operator's preferred mechanism (jackpot-iac for cloud deployments).

### NCBI submission (I-3a/b)

| Key | Required | Notes |
|---|---|---|
| `ncbi_submission_username` | when `allow_backend_submission` ∧ `NCBI` in `backend_submission_repos` | NCBI submission portal account. |
| `ncbi_submission_password` | same | Paired password. |
| `ncbi_api_key` | same | Optional but strongly recommended for rate limiting. |

NCBI submission accounts are obtained via the BioProject submission
portal. Backend execution writes to the same account regardless of
which lab triggers the submission, so operators should provision a
JACKPOT-specific account with appropriate review workflows.

### ENA submission (I-3a/b)

| Key | Required | Notes |
|---|---|---|
| `ena_webin_username` | when `allow_backend_submission` ∧ `ENA` in `backend_submission_repos` | ENA Webin submitter account. |
| `ena_webin_password` | same | Paired password. |

### GISAID submission (I-3 future)

GISAID requires a per-submitter account; backend execution is not yet
supported in v1 (the package generator produces a GISAID-ready bundle
the operator uploads themselves). The credential keys
`gisaid_username` / `gisaid_client_id` / `gisaid_client_secret` are
reserved in the registry for when backend execution lands.

### DDBJ submission (I-3 future)

Same status as GISAID. Reserved keys: `ddbj_submitter_id`,
`ddbj_password`.

### Federation peer authentication (B-FED-1, future)

| Key | Required | Notes |
|---|---|---|
| `federation_private_key_path` | when `federation_enabled=true` | Path to the ed25519 private key (0600). |
| `federation_ca_cert_path` | optional | When the federation network uses a central CA, path to the CA cert. |

Federation supports ed25519 keypairs (default, generated by
`jackpot init secrets`) and CA-cert auth (B-FED-1 trigger). Both are
read via the credential facade so a federation network growing past
the local-keypair model can layer the CA on without consumer-code
changes.

### LLM assistant (Year 2 future)

| Key | Required | Notes |
|---|---|---|
| `anthropic_api_key` | when `assistant_enabled=true` ∧ `assistant_backend="anthropic"` | Anthropic API key for the support assistant. |
| `ollama_endpoint` | when `assistant_enabled=true` ∧ `assistant_backend="ollama"` | Ollama service URL (not strictly a secret, but routed through the facade for consistency). |

## Rotation patterns

- **`env`:** stop the container, update the env var, restart. Cache
  TTL (default 5 minutes) means a rolling rotation is also possible
  by updating env vars on new pods and letting old pods drain.
- **`file`:** edit the YAML file in place; the facade's TTL'd cache
  picks up the new value within `credential_cache_ttl_seconds`. No
  process restart needed for routine rotation.
- **`gcp_secret_manager`:** add a new secret version
  (`gcloud secrets versions add ...`); the backend uses the
  `latest` alias by default. Cache TTL controls visibility delay.

After a credential rotation that involves access-token revocation
upstream (e.g. NCBI portal password change), call
`credentials.invalidate_all()` from a Platform Admin endpoint or
restart the API to flush cached values immediately.

## Diagnostics

`credentials.list_keys()` returns the configured credentials visible
to the active backend (env: matching env vars; file: YAML keys; GCP:
secrets matching the prefix). Use it for `jackpot doctor`-style
checks; it does NOT return values.

The `backend.credentials.audit` stdlib logger emits
`CREDENTIAL_READ` / `CREDENTIAL_READ_FAILED` events on every read
attempt with `{key, backend, reason}` extras. Log aggregators should
capture this stream the same way they capture other backend logs.

## What's next — future backends

The factory dispatches by `Settings.credential_backend` literal. New
backends register by:

1. Implementing `CredentialBackend` in `backend/credentials/<name>_backend.py`.
2. Adding the literal to the `credential_backend` `Literal[...]` annotation.
3. Adding the dispatch case to `CredentialFactory`.
4. Adding per-backend Settings fields if the backend needs them
   (path, prefix, region, etc.).
5. Documenting the backend in this file and in [`spec.md`](../../spec.md)
   Phase C-1.

Planned: **AWS Secrets Manager** (Scenario E AWS-hosted), **Azure Key
Vault** (Azure-hosted), **OS keychain** (macOS Keychain / Windows
Credential Manager / freedesktop Secret Service for Scenario A
operators who want OS-managed plaintext-free storage). No consumer
code changes when these land.
