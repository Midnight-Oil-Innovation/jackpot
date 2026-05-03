"""
jackpot.cli.files
~~~~~~~~~~~~~~~~~
``jackpot files`` command group.

Commands:
  jackpot files promote   — promote a file to MANAGED or MIRRORED
  jackpot files verify    — re-verify a file (or every file on a sample)
  jackpot files list      — list files (storage_state, project, sample filters)
  jackpot files get       — show one file's full row

Phase P0f F-9. The promote command supports two locator forms — a
direct ``--file-id`` and a sample-plus-role lookup — and an optional
``--wait`` flag that polls the job-status endpoint until completion or
``--timeout`` (default 600 s).
"""

from __future__ import annotations

import time

import click
from rich.console import Console
from rich.table import Table

from jackpot.cli.config import get_client_credentials
from jackpot.core.client import JACKPOTClient
from jackpot.core.exceptions import ConfigError, JACKPOTError

console = Console()

_VALID_TARGETS = ("managed", "mirrored")
_VALID_RETENTIONS = ("standard", "long_term", "ephemeral")
_TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED"})


def _get_client() -> JACKPOTClient:
    try:
        api_url, token = get_client_credentials()
        return JACKPOTClient(api_url=api_url, token=token)
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


def _resolve_file_id(client: JACKPOTClient, sample: str, role: str) -> int:
    """Look up ``sample_files.id`` for ``(sample, role)`` via the API.

    Uses ``GET /api/v1/samples/{sample}`` to resolve the sample's
    integer id, then ``GET /api/v1/files/?sample_id=...`` filtered to
    the requested role on the client side. There may be multiple files
    per role across re-uploads; the most recent (highest ``id``) wins.
    """
    sample_payload = client.get(f"/api/v1/samples/{sample}")
    if isinstance(sample_payload, list):
        # Defensive: some samples endpoints return list shapes
        sample_payload = sample_payload[0] if sample_payload else {}
    sample_int_id = sample_payload.get("id")
    if not sample_int_id:
        raise click.ClickException(f"Could not resolve sample {sample!r} to an integer id.")

    rows = client.get("/api/v1/files/", params={"sample_id": sample_int_id, "per_page": 200})
    items = rows if isinstance(rows, list) else rows.get("data", [])
    role_upper = role.upper()
    matches = [r for r in items if (r.get("read_direction") or "").upper() == role_upper]
    if not matches:
        # Fall back to file_type-based match for outputs (where role is
        # OTHER but the user remembers the file by type).
        matches = [r for r in items if (r.get("file_type") or "").lower() == role.lower()]
    if not matches:
        raise click.ClickException(
            f"No file found for sample {sample!r} with role {role!r}. "
            "Use `jackpot files list --sample-id <int>` to inspect available files."
        )
    return max(matches, key=lambda r: r.get("id") or 0)["id"]


def _poll_job(client: JACKPOTClient, job_id: str, timeout: int) -> dict:
    """Block until ``job_id`` reaches a terminal status or ``timeout`` elapses.

    Polls every two seconds. Raises ``click.ClickException`` on timeout
    so the CLI exits non-zero. Returns the final status dict on success.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status = client.get(f"/api/v1/files/jobs/{job_id}")
        except JACKPOTError:
            # The tracker is in-memory; a 404 right after scheduling
            # means the worker hasn't picked it up yet on this instance.
            # Treat as transient until the deadline.
            time.sleep(2)
            continue
        if isinstance(status, dict) and status.get("status") in _TERMINAL_STATUSES:
            return status
        time.sleep(2)
    raise click.ClickException(
        f"Promotion job {job_id} did not complete within {timeout}s "
        "(server may still be working — re-poll with `jackpot files get` "
        "or check audit log)."
    )


@click.group()
def files() -> None:
    """Manage file references (storage state, verification)."""


@files.command("promote")
@click.option("--file-id", type=int, default=None, help="sample_files.id of the file to promote")
@click.option("--sample", type=str, default=None, help="Sample ID (use with --role)")
@click.option(
    "--role", type=str, default=None, help="File role (R1, R2, ASSEMBLY, etc.); use with --sample"
)
@click.option("--to", type=click.Choice(_VALID_TARGETS), required=True)
@click.option("--retention", type=click.Choice(_VALID_RETENTIONS), default="standard")
@click.option("--wait", is_flag=True, default=False, help="Block until promotion completes")
@click.option("--timeout", type=int, default=600, show_default=True)
@click.option(
    "--json", "output_json", is_flag=True, default=False, help="Emit JSON instead of a table"
)
def promote(
    file_id: int | None,
    sample: str | None,
    role: str | None,
    to: str,
    retention: str,
    wait: bool,
    timeout: int,
    output_json: bool,
) -> None:
    """Promote a file from EXTERNAL/MIRRORED to MANAGED or MIRRORED.

    \b
    Examples:
      jackpot files promote --file-id 9001 --to managed
      jackpot files promote --sample EX-2026-001 --role R1 --to managed --wait
      jackpot files promote --file-id 9001 --to mirrored --retention long_term
    """
    if file_id is None and not (sample and role):
        raise click.UsageError(
            "Specify either --file-id or both --sample and --role to identify the file."
        )
    if file_id is not None and (sample or role):
        raise click.UsageError(
            "Pass --file-id OR --sample/--role, not both, to avoid ambiguous resolution."
        )

    client = _get_client()
    if file_id is None:
        file_id = _resolve_file_id(client, sample, role)  # type: ignore[arg-type]

    body = {"to": to.upper(), "retention_policy": retention.upper()}
    try:
        raw = client.post(f"/api/v1/files/{file_id}/promote", json=body)
    except JACKPOTError as exc:
        click.echo(f"Promote failed: {exc}", err=True)
        raise SystemExit(1) from exc
    result: dict = raw if isinstance(raw, dict) else {}

    if not wait:
        if output_json:
            import json

            click.echo(json.dumps(result, indent=2))
            return
        click.echo(
            f"Queued promote job {result.get('job_id')} for file {file_id}: "
            f"{result.get('current_state')} → {result.get('target_state')} "
            f"(estimated {result.get('estimated_seconds')}s). "
            f"Poll with `jackpot files get --file-id {file_id}` or pass --wait next time."
        )
        return

    final = _poll_job(client, result["job_id"], timeout)
    if output_json:
        import json

        click.echo(json.dumps(final, indent=2))
        return
    if final.get("status") == "COMPLETED" and final.get("outcome") in ("SUCCESS", "NOOP"):
        click.echo(
            f"Promote complete: file {file_id} now {result['target_state']} "
            f"({final.get('copied_bytes', 0)} bytes in "
            f"{final.get('elapsed_seconds', 0):.1f}s)."
        )
    else:
        err = final.get("error") or "unknown"
        click.echo(f"Promote failed for file {file_id}: {err}", err=True)
        raise SystemExit(1)


@files.command("verify")
@click.option("--file-id", type=int, default=None, help="Verify a single file by id")
@click.option(
    "--sample",
    type=str,
    default=None,
    help="Verify every file on this sample (sample_id string)",
)
@click.option(
    "--json", "output_json", is_flag=True, default=False, help="Emit JSON instead of a table"
)
def verify(file_id: int | None, sample: str | None, output_json: bool) -> None:
    """Force a synchronous re-verification of a file or every file on a sample.

    \b
    Examples:
      jackpot files verify --file-id 9001
      jackpot files verify --sample EX-2026-001
    """
    if file_id is None and sample is None:
        raise click.UsageError("Specify --file-id or --sample to identify what to verify.")
    if file_id is not None and sample is not None:
        raise click.UsageError("Pass --file-id OR --sample, not both.")

    client = _get_client()
    targets: list[int]
    if file_id is not None:
        targets = [file_id]
    else:
        sample_payload = client.get(f"/api/v1/samples/{sample}")
        if isinstance(sample_payload, list):
            sample_payload = sample_payload[0] if sample_payload else {}
        sample_int_id = sample_payload.get("id")
        if not sample_int_id:
            raise click.ClickException(f"Could not resolve sample {sample!r} to an integer id.")
        rows = client.get("/api/v1/files/", params={"sample_id": sample_int_id, "per_page": 200})
        items = rows if isinstance(rows, list) else rows.get("data", [])
        targets = [r["id"] for r in items if r.get("id") is not None]
        if not targets:
            click.echo(f"No files found on sample {sample!r}.")
            return

    results = []
    for fid in targets:
        try:
            r = client.post(f"/api/v1/files/{fid}/verify")
        except JACKPOTError as exc:
            click.echo(f"Verify failed for file {fid}: {exc}", err=True)
            continue
        if isinstance(r, list):
            r = r[0] if r else {}
        results.append(r)

    if output_json:
        import json

        click.echo(json.dumps(results, indent=2))
        return

    table = Table(title="Verification results")
    table.add_column("file_id", style="cyan")
    table.add_column("uri")
    table.add_column("storage_state", style="green")
    table.add_column("status")
    table.add_column("verified_at")
    for r in results:
        table.add_row(
            str(r.get("file_id", "")),
            r.get("uri", ""),
            r.get("storage_state", ""),
            r.get("last_verification_status", ""),
            r.get("last_verified_at", "") or "",
        )
    console.print(table)


@files.command("list")
@click.option(
    "--storage-state",
    type=click.Choice(["EXTERNAL", "MANAGED", "MIRRORED", "STAGED", "BROKEN"]),
    default=None,
)
@click.option("--sample-id", type=int, default=None, help="samples.id (integer) to filter on")
@click.option("--project", type=int, default=None, help="Filter by project id")
@click.option("--page", type=int, default=1)
@click.option("--per-page", type=int, default=50)
@click.option(
    "--json", "output_json", is_flag=True, default=False, help="Emit JSON instead of a table"
)
def files_list(
    storage_state: str | None,
    sample_id: int | None,
    project: int | None,
    page: int,
    per_page: int,
    output_json: bool,
) -> None:
    """List files visible to the caller, with optional filters."""
    client = _get_client()
    params: dict = {"page": page, "per_page": per_page}
    if storage_state:
        params["storage_state"] = storage_state
    if sample_id:
        params["sample_id"] = sample_id
    if project:
        params["project_id"] = project

    response = client.get("/api/v1/files/", params=params)
    items = response if isinstance(response, list) else response.get("data", [])

    if output_json:
        import json

        click.echo(json.dumps(items, indent=2))
        return
    if not items:
        click.echo("No files found.")
        return

    table = Table(title=f"Files (page {page})")
    table.add_column("id", style="cyan")
    table.add_column("filename")
    table.add_column("size_bytes")
    table.add_column("storage_state", style="green")
    table.add_column("last_verified_at")
    table.add_column("sample_id")
    for f in items:
        table.add_row(
            str(f.get("id", "")),
            f.get("filename", "") or "",
            str(f.get("file_size_bytes", "") or ""),
            f.get("storage_state", "") or "",
            f.get("last_verified_at", "") or "",
            f.get("sample_id", "") or "",
        )
    console.print(table)


@files.command("get")
@click.option("--file-id", type=int, required=True)
@click.option(
    "--json", "output_json", is_flag=True, default=False, help="Emit JSON instead of a summary"
)
def files_get(file_id: int, output_json: bool) -> None:
    """Show a single file's full row plus the samples that reference it."""
    client = _get_client()
    raw = client.get(f"/api/v1/files/{file_id}")
    result: dict = raw if isinstance(raw, dict) else {}
    if output_json:
        import json

        click.echo(json.dumps(result, indent=2))
        return
    for key, label in [
        ("id", "ID"),
        ("filename", "Filename"),
        ("uri", "Primary URI"),
        ("alternate_uris", "Alternate URIs"),
        ("original_uri", "Original URI"),
        ("file_type", "File type"),
        ("file_size_bytes", "Size (bytes)"),
        ("storage_state", "Storage state"),
        ("retention_policy", "Retention policy"),
        ("last_verified_at", "Last verified"),
        ("last_verification_status", "Verification status"),
    ]:
        val = result.get(key)
        if val is not None and val != "":
            click.echo(f"  {label:<22} {val}")
    samples = result.get("samples") or []
    if samples:
        click.echo("  Referenced by samples:")
        for s in samples:
            click.echo(
                f"    - {s.get('sample_id', '?')} (project={s.get('project_id')}, "
                f"lab={s.get('lab_id')})"
            )
