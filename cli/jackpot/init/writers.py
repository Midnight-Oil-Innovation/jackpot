"""
File emitters for `jackpot init configure`.

Per design doc Decision 6: writes `instances/<name>/{jackpot.toml,
.env.local, values.local.yaml, seed.sql, README.md}`. Idempotency
contract from Decision 7: secret files (anything under `secrets/`)
are never silently overwritten — that's enforced in writers.py too,
since the same path-classification logic applies to any future writer.

Operator-customisable fields land in jackpot.toml's `[operator]` block;
scenario defaults land in `[defaults]` for diffing on `reconfigure`.
"""

from __future__ import annotations

import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import toml
import yaml
from jackpot_scenarios.scenarios import (
    CURRENT_SCHEMA_VERSION,
    SECRET_FIELD_NAMES,
    Scenario,
    ScenarioDefaults,
)


# Files that hold or generate SECRET values. Any path matching either
# rule below is treated as a secret per Decision 7 (never silently
# overwritten on re-run; --regenerate-secrets prompts per-file).
def is_secret_path(path: Path) -> bool:
    """True if `path` is inside a `secrets/` directory or its filename
    matches a known-secret pattern."""
    if any(part == "secrets" for part in path.parts):
        return True
    return path.name in {
        "federation_private_key.pem",
        "jwt_signing_key.txt",
        "oauth_client_secret.txt",
    }


def write_with_idempotency_check(
    path: Path,
    content: str,
    *,
    regenerate_secrets: bool = False,
    overwrite_non_secrets: bool = True,
) -> bool:
    """Write `content` to `path`. Returns True if the file was written,
    False if it was preserved (existing secret + no regenerate).

    - Secret paths (per `is_secret_path`) are preserved unless
      `regenerate_secrets=True`.
    - Non-secret paths are overwritten by default; pass
      `overwrite_non_secrets=False` to preserve existing content
      (used by `reconfigure` to avoid clobbering operator edits).
    """
    if path.exists():
        if is_secret_path(path) and not regenerate_secrets:
            return False
        if not is_secret_path(path) and not overwrite_non_secrets:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    if is_secret_path(path):
        # 0600 — owner read/write only. Filesystem-level enforcement
        # of "secrets are not for the world."
        path.chmod(0o600)
    return True


# ── jackpot.toml ─────────────────────────────────────────────────────────


def render_jackpot_toml(
    *,
    scenario: Scenario,
    operator_overrides: dict[str, Any],
    instance_name: str,
    jackpot_version: str = "5.0.0",
) -> str:
    """Build the canonical instance-config TOML.

    `operator_overrides` is the dict of fields the operator typed values
    for at the configure prompts (host_organization_name, etc.) — these
    override the scenario defaults at runtime via the [operator] block.
    """
    now_iso = datetime.now(UTC).isoformat(timespec="seconds")

    payload: dict[str, Any] = {
        "meta": {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "created_at": now_iso,
            "created_by_jackpot_version": jackpot_version,
            "last_reconfigured_at": now_iso,
            "instance_name": instance_name,
        },
        "scenario": {
            "code": scenario.code,
            "name": scenario.name,
        },
        "operator": _serialise_operator_block(operator_overrides),
        "defaults": _serialise_defaults_block(scenario.defaults, operator_overrides),
    }
    return toml.dumps(payload)


def _serialise_operator_block(overrides: dict[str, Any]) -> dict[str, Any]:
    """The [operator] block holds only fields the operator explicitly
    set. Filters out None and empty strings."""
    filtered = {}
    for k, v in overrides.items():
        if v is None or v == "":
            continue
        if isinstance(v, list) and not v:
            continue
        if k in SECRET_FIELD_NAMES:
            # Secrets do not land in the [operator] TOML block — they
            # live in instances/<name>/secrets/ files (per Decision 5).
            continue
        filtered[k] = v
    return filtered


def _serialise_defaults_block(
    defaults: ScenarioDefaults,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """The [defaults] block records every scenario-default value. Used
    by `reconfigure` to diff against current scenario defaults when the
    schema_version changes."""
    dumped = defaults.model_dump()
    # Strip secrets — they have no place in the TOML.
    return {k: v for k, v in dumped.items() if k not in SECRET_FIELD_NAMES}


# ── .env.local ───────────────────────────────────────────────────────────


def render_env_local(
    *,
    scenario: Scenario,
    operator_overrides: dict[str, Any],
    instance_dir: Path,
) -> str:
    """Build the docker-compose `.env.local` for this instance.

    Resolves scenario defaults + operator overrides into the env-var
    keys backend/backend/config.py reads. Compose profiles per Decision 2.
    Secret values are referenced as ${{secret:KEY}}-style placeholders;
    docker-compose doesn't natively interpolate those — operators source
    a separate secret-loader before `docker compose up`. The placeholder
    presence at least surfaces what secrets are required.
    """
    defaults = scenario.defaults
    resolved = _resolve_field_values(defaults, operator_overrides)

    env_lines: list[str] = [
        f"# Generated by `jackpot init configure` for instance {instance_dir.name!r}.",
        f"# Scenario: {scenario.code} ({scenario.name})",
        "# Edit at your own risk; `jackpot init reconfigure` will regenerate.",
        "",
        "# ── Compose profile ─────────────────────────────────────────────────",
        f"COMPOSE_PROFILES={defaults.compose_profile}",
        "",
        "# ── Backend identity ───────────────────────────────────────────────",
        f"ENV={'gcp' if defaults.storage_backend in {'gcs', 's3'} else 'local'}",
        f"HOST_ORGANIZATION_NAME={resolved.get('host_organization_name', '')}",
        f"JACKPOT_API_URL={resolved.get('deployment_url', 'http://localhost:8000')}",
        "",
        "# ── Auth ───────────────────────────────────────────────────────────",
        f"MOCK_USER_EMAIL={resolved.get('host_organization_email', 'admin@example.org')}",
        f"GOOGLE_OAUTH_REDIRECT_URL={'postmessage' if defaults.auth_method == 'oauth' else ''}",
        "",
        "# ── Storage ────────────────────────────────────────────────────────",
        f"STORAGE_ENDPOINT={'http://minio:9000' if defaults.storage_backend == 'minio' else ''}",
        f"STORAGE_BUCKET_SEQUENCES={defaults.bucket_sequences}",
        f"STORAGE_BUCKET_RAW={defaults.bucket_raw}",
        f"STORAGE_BUCKET_STAGING={defaults.bucket_staging}",
        f"STORAGE_BUCKET_DATASETS={defaults.bucket_datasets}",
        f"STORAGE_BUCKET_SUBMISSIONS={defaults.bucket_submissions}",
        f"WORK_BUCKET={defaults.bucket_work}",
        f"RESULTS_BUCKET={defaults.bucket_results}",
        "",
        "# ── Pipeline executor ─────────────────────────────────────────────",
        f"PIPELINE_EXECUTOR={defaults.pipeline_executor}",
        "",
        "# ── Background jobs + DLP ─────────────────────────────────────────",
        f"SCHEDULER_ENABLED={'true' if defaults.scheduler_enabled else 'false'}",
        f"DLP_ENABLED={'true' if defaults.dlp_enabled else 'false'}",
        "",
        "# ── CORS ───────────────────────────────────────────────────────────",
        f"CORS_ORIGINS={','.join(resolved.get('cors_origins', []))}",
        "",
        "# ── Rate limiting ─────────────────────────────────────────────────",
        f"RATE_LIMIT_ENABLED={'true' if defaults.rate_limit_enabled else 'false'}",
        f"RATE_LIMIT_AUTH={defaults.rate_limit_auth}",
        f"RATE_LIMIT_INGEST={defaults.rate_limit_ingest}",
        "",
        "# ── Secrets (sourced from instances/<name>/secrets/ at runtime) ───",
        "# SECRET_KEY: see secrets/jwt_signing_key.txt",
        "# GOOGLE_OAUTH_CLIENT_SECRET: see secrets/oauth_client_secret.txt",
        "# NCBI_API_KEY: operator-provided",
        "# JACKPOT_API_TOKEN: operator-provided",
    ]
    return "\n".join(env_lines) + "\n"


def _resolve_field_values(
    defaults: ScenarioDefaults,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Merge scenario defaults with operator overrides. Overrides win
    when set to a non-empty value."""
    resolved = defaults.model_dump()
    for k, v in overrides.items():
        if v is None or v == "":
            continue
        if isinstance(v, list) and not v:
            continue
        resolved[k] = v
    return resolved


# ── values.local.yaml ────────────────────────────────────────────────────


def render_values_local_yaml(
    *,
    scenario: Scenario,
    operator_overrides: dict[str, Any],
) -> str:
    """Build the Helm values overlay for cloud scenarios (B/C/D/E/T).

    For laptop / CI scenarios, the file is still written but minimal —
    operators using `helm install` for those scenarios is uncommon but
    not forbidden.
    """
    defaults = scenario.defaults
    resolved = _resolve_field_values(defaults, operator_overrides)

    payload: dict[str, Any] = {
        "replicaCount": defaults.replica_count,
        "env": {
            "ENV": "gcp" if defaults.storage_backend in {"gcs", "s3"} else "local",
            "STORAGE_BACKEND": defaults.storage_backend,
            "PIPELINE_EXECUTOR": defaults.pipeline_executor,
            "DLP_ENABLED": "true" if defaults.dlp_enabled else "false",
            "SCHEDULER_ENABLED": "true" if defaults.scheduler_enabled else "false",
            "JACKPOT_API_URL": resolved.get("deployment_url", ""),
            "CORS_ORIGINS": ",".join(resolved.get("cors_origins", [])),
            "RATE_LIMIT_ENABLED": "true" if defaults.rate_limit_enabled else "false",
            "RATE_LIMIT_AUTH": defaults.rate_limit_auth,
            "RATE_LIMIT_INGEST": defaults.rate_limit_ingest,
        },
        "buckets": {
            "STORAGE_BUCKET_SEQUENCES": defaults.bucket_sequences,
            "STORAGE_BUCKET_RAW": defaults.bucket_raw,
            "STORAGE_BUCKET_STAGING": defaults.bucket_staging,
            "STORAGE_BUCKET_DATASETS": defaults.bucket_datasets,
            "STORAGE_BUCKET_SUBMISSIONS": defaults.bucket_submissions,
            "WORK_BUCKET": defaults.bucket_work,
            "RESULTS_BUCKET": defaults.bucket_results,
        },
    }

    header = (
        f"# Helm values overlay generated by `jackpot init configure`\n"
        f"# for scenario {scenario.code} ({scenario.name}).\n"
        "# Pass to helm with: helm upgrade --values instances/<name>/values.local.yaml ...\n\n"
    )
    return header + yaml.safe_dump(payload, sort_keys=False)


# ── seed.sql ─────────────────────────────────────────────────────────────


def render_seed_sql(
    *,
    scenario: Scenario,
    operator_overrides: dict[str, Any],
    instance_dir: Path,
) -> str:
    """Generate idempotent post-alembic seed SQL.

    Per Decision 6: jackpot init owns the seed-data layer. The baseline
    migration seeds Example Org / Example Lab / admin@example.org /
    Example Sequencing Lab / Example Reference Lab; this seed.sql renames
    those rows to operator-supplied names. Idempotent (WHERE matches old
    OR new value) so re-running on an already-seeded DB is safe.
    """
    org_name = operator_overrides.get("host_organization_name") or ""
    op_email = operator_overrides.get("host_organization_email") or ""

    if not org_name and not op_email:
        # Scenario A / F may legitimately accept the Example defaults —
        # still emit the file but with an explanatory header and no
        # UPDATE statements. Avoids confusing operators with an empty
        # file.
        body = (
            "-- No operator-specific identity values provided. The "
            "baseline migration's seed data ('Example Org' / 'Example Lab' "
            "/ 'admin@example.org') is used as-is.\n"
            "--\n"
            "-- To seed real operator names, rerun:\n"
            "--   jackpot init reconfigure --instance " + instance_dir.name + "\n"
            "-- and provide values at the prompts.\n"
        )
    else:
        statements: list[str] = []
        if org_name:
            safe_org = _sql_escape(org_name)
            statements.append(
                f"UPDATE organizations SET display_name = '{safe_org}' "
                f"WHERE display_name = 'Example Org' OR display_name = '{safe_org}';"
            )
        if op_email:
            safe_email = _sql_escape(op_email)
            statements.append(
                f"UPDATE users SET email = '{safe_email}' "
                f"WHERE email = 'admin@example.org' OR email = '{safe_email}';"
            )
        body = "\n".join(statements) + "\n"

    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    header = textwrap.dedent(
        f"""\
        -- Generated by `jackpot init configure` on {timestamp}
        -- Instance: {instance_dir.name}
        -- Scenario: {scenario.code} ({scenario.name})
        -- Apply with:  psql -f {instance_dir.name}/seed.sql
        --   or via:    jackpot init bootstrap --instance {instance_dir.name}
        --
        -- Idempotent: re-running on an already-seeded DB is a no-op
        -- because each UPDATE matches both the original Example value and
        -- the post-rename operator value.

        """
    )
    return header + body


def _sql_escape(value: str) -> str:
    """Minimal SQL string escape — replace single quotes. Sufficient for
    PostgreSQL identifier strings; not safe for arbitrary user input,
    but the inputs here come from prompts to a trusted operator."""
    return value.replace("'", "''")


# ── README.md ────────────────────────────────────────────────────────────


def render_readme_md(
    *,
    scenario: Scenario,
    instance_name: str,
) -> str:
    """Auto-generated per-instance README explaining what this directory
    is and how to use it."""
    return textwrap.dedent(
        f"""\
        # JACKPOT instance — `{instance_name}`

        Generated by `jackpot init configure` on {datetime.now(UTC).strftime('%Y-%m-%d')}.

        ## Scenario

        **{scenario.code} — {scenario.name}**

        {scenario.description}

        ## Files

        - `jackpot.toml` — canonical instance config (scenario + operator overrides)
        - `.env.local` — docker-compose env vars
        - `values.local.yaml` — Helm values overlay (cloud scenarios)
        - `seed.sql` — operator seed data applied post-`alembic upgrade head`
        - `secrets/` — generated secrets (0600 perms, gitignored)

        ## Bootstrap

        ```bash
        jackpot init bootstrap --instance {instance_name}
        ```

        Runs alembic + applies seed.sql + smoke-tests `/health`.

        ## Reconfigure

        ```bash
        jackpot init reconfigure --instance {instance_name}
        ```

        Re-runs configure preserving secrets. Use `--regenerate-secrets`
        to rotate (per-secret confirmation prompts).
        """
    )


# ── orchestration ────────────────────────────────────────────────────────


def write_instance(
    *,
    scenario: Scenario,
    operator_overrides: dict[str, Any],
    instance_dir: Path,
    overwrite_non_secrets: bool = True,
) -> dict[str, bool]:
    """Write all 5 instance files. Returns a {filename: was_written} map
    so callers can report which files changed.

    Does NOT generate secrets — that's `jackpot init secrets` (B.2.4)."""
    instance_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, bool] = {}

    written["jackpot.toml"] = write_with_idempotency_check(
        instance_dir / "jackpot.toml",
        render_jackpot_toml(
            scenario=scenario,
            operator_overrides=operator_overrides,
            instance_name=instance_dir.name,
        ),
        overwrite_non_secrets=overwrite_non_secrets,
    )
    written[".env.local"] = write_with_idempotency_check(
        instance_dir / ".env.local",
        render_env_local(
            scenario=scenario,
            operator_overrides=operator_overrides,
            instance_dir=instance_dir,
        ),
        overwrite_non_secrets=overwrite_non_secrets,
    )
    written["values.local.yaml"] = write_with_idempotency_check(
        instance_dir / "values.local.yaml",
        render_values_local_yaml(
            scenario=scenario,
            operator_overrides=operator_overrides,
        ),
        overwrite_non_secrets=overwrite_non_secrets,
    )
    written["seed.sql"] = write_with_idempotency_check(
        instance_dir / "seed.sql",
        render_seed_sql(
            scenario=scenario,
            operator_overrides=operator_overrides,
            instance_dir=instance_dir,
        ),
        overwrite_non_secrets=overwrite_non_secrets,
    )
    written["README.md"] = write_with_idempotency_check(
        instance_dir / "README.md",
        render_readme_md(
            scenario=scenario,
            instance_name=instance_dir.name,
        ),
        overwrite_non_secrets=overwrite_non_secrets,
    )

    # Always create the secrets/ subdir (with 0700 perms) even if
    # B.2.4 hasn't generated anything in it yet.
    secrets_dir = instance_dir / "secrets"
    if not secrets_dir.exists():
        secrets_dir.mkdir(mode=0o700)

    return written


__all__ = [
    "is_secret_path",
    "render_env_local",
    "render_jackpot_toml",
    "render_readme_md",
    "render_seed_sql",
    "render_values_local_yaml",
    "write_instance",
    "write_with_idempotency_check",
]
