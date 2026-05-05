"""
jackpot.cli.submissions
~~~~~~~~~~~~~~~~~~~~~~~
``jackpot submissions`` command group.

Exposes the full submission lifecycle to the command line: create,
attach samples, validate, generate the package, run backend execution
(I-3c), retry, view per-attempt logs, register accessions, withdraw.

Mirrors :mod:`jackpot.sdk.submissions`. CLI commands are thin shells:
parse arguments, call the SDK method, format the response.
"""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from jackpot.cli.config import get_client_credentials
from jackpot.core.client import JACKPOTClient
from jackpot.core.exceptions import (
    ConflictError,
    JACKPOTError,
    NotFoundError,
)
from jackpot.sdk.submissions import SubmissionsModule

console = Console()


def _module() -> SubmissionsModule:
    api_url, token = get_client_credentials()
    return SubmissionsModule(JACKPOTClient(api_url=api_url, token=token))


def _print_json(data: Any) -> None:
    click.echo(_json.dumps(data, indent=2, default=str))


def _handle_error(exc: Exception, action: str) -> None:
    """Print a friendly error and exit non-zero.

    The 4xx-with-error-code messages from the I-3c endpoints are already
    operator-friendly (the server constructs them that way); we surface
    them as-is. NETWORK / AUTH / SERVER errors get a one-line preamble
    so the operator knows what stage failed.
    """
    if isinstance(exc, ConflictError):
        click.echo(f"{action} failed: {exc}", err=True)
    elif isinstance(exc, NotFoundError):
        click.echo(f"{action} failed: submission not found.", err=True)
    elif isinstance(exc, JACKPOTError):
        click.echo(f"{action} failed: {exc}", err=True)
    else:
        click.echo(f"{action} failed: {exc}", err=True)
    raise SystemExit(2)


# ── Click group ───────────────────────────────────────────────────────


@click.group()
def submissions() -> None:
    """Manage submissions to NCBI, GISAID, ENA, and DDBJ."""


# ── create / list / show / update / delete ──────────────────────────


@submissions.command("create")
@click.option("--title", required=True, help="Submission title.")
@click.option(
    "--target-repo",
    "target_repo",
    required=True,
    type=click.Choice(
        [
            "NCBI",
            "GISAID_EPICOV",
            "GISAID_EPIFLU",
            "GISAID_EPIPOX",
            "ENA",
            "DDBJ",
        ],
        case_sensitive=False,
    ),
    help="Target repository.",
)
@click.option("--lab-id", "lab_id", required=True, type=int, help="Lab to scope under.")
@click.option(
    "--samples",
    "sample_ids_str",
    required=True,
    help="Comma-separated sample IDs (e.g. 1,2,3) or repeat the flag.",
    multiple=True,
)
@click.option("--description", default=None, help="Optional human description.")
@click.option(
    "--bioproject",
    "bioproject_accession",
    default=None,
    help="Existing BioProject accession to associate with this submission.",
)
@click.option(
    "--release-date",
    default=None,
    help="ISO date for embargo / release scheduling (YYYY-MM-DD).",
)
def submissions_create(
    title: str,
    target_repo: str,
    lab_id: int,
    sample_ids_str: tuple[str, ...],
    description: str | None,
    bioproject_accession: str | None,
    release_date: str | None,
) -> None:
    """Create a DRAFT submission and attach samples."""
    sample_ids: list[int] = []
    for raw in sample_ids_str:
        for piece in raw.split(","):
            piece = piece.strip()
            if not piece:
                continue
            try:
                sample_ids.append(int(piece))
            except ValueError:
                click.echo(f"Invalid sample ID {piece!r}; expected integer.", err=True)
                raise SystemExit(2) from None
    if not sample_ids:
        click.echo("At least one --samples value is required.", err=True)
        raise SystemExit(2)

    try:
        sub = _module().create(
            title=title,
            target_repository=target_repo.upper(),
            lab_id=lab_id,
            sample_ids=sample_ids,
            description=description,
            bioproject_accession=bioproject_accession,
            release_date=release_date,
        )
    except Exception as exc:
        _handle_error(exc, "Create submission")
        return
    click.echo(
        f"Created submission {sub['id']} ({sub.get('title')}) status={sub.get('status')}"
    )


@submissions.command("list")
@click.option("--lab-id", "lab_id", type=int, default=None)
@click.option("--status", default=None)
@click.option(
    "--target-repo",
    "target_repository",
    default=None,
    type=click.Choice(
        [
            "NCBI",
            "GISAID_EPICOV",
            "GISAID_EPIFLU",
            "GISAID_EPIPOX",
            "ENA",
            "DDBJ",
        ],
        case_sensitive=False,
    ),
)
@click.option("--page", type=int, default=1)
@click.option("--per-page", type=int, default=50)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    default=False,
    help="Output as JSON instead of a table.",
)
def submissions_list(
    lab_id: int | None,
    status: str | None,
    target_repository: str | None,
    page: int,
    per_page: int,
    output_json: bool,
) -> None:
    """List submissions in a lab, optionally filtered by status / repo."""
    try:
        rows = _module().list(
            lab_id=lab_id,
            status=status,
            target_repository=target_repository.upper() if target_repository else None,
            page=page,
            per_page=per_page,
        )
    except Exception as exc:
        _handle_error(exc, "List submissions")
        return

    if output_json:
        _print_json(rows)
        return

    if not rows:
        click.echo("No submissions found.")
        return

    table = Table(title=f"Submissions (page {page})")
    table.add_column("id", style="cyan")
    table.add_column("title")
    table.add_column("repo")
    table.add_column("status", style="green")
    table.add_column("samples")
    table.add_column("created")
    for r in rows:
        created = r.get("created_at") or ""
        table.add_row(
            str(r.get("id", "")),
            r.get("title", ""),
            r.get("target_repository", ""),
            r.get("status", ""),
            str(r.get("sample_count", "")),
            created[:10] if isinstance(created, str) else "",
        )
    console.print(table)


@submissions.command("show")
@click.argument("submission_id", type=int)
@click.option("--json", "output_json", is_flag=True, default=False)
def submissions_show(submission_id: int, output_json: bool) -> None:
    """Show one submission with its sample attachment."""
    try:
        sub = _module().get(submission_id)
    except Exception as exc:
        _handle_error(exc, "Show submission")
        return

    if output_json:
        _print_json(sub)
        return

    for key, label in [
        ("id", "ID"),
        ("title", "Title"),
        ("target_repository", "Repository"),
        ("status", "Status"),
        ("created_at", "Created"),
        ("package_path", "Package path"),
        ("execution_attempt_count", "Execution attempts"),
        ("execution_started_at", "Execution started"),
        ("execution_completed_at", "Execution completed"),
        ("execution_error_message", "Execution error"),
    ]:
        val = sub.get(key)
        if val is not None and val != "":
            click.echo(f"  {label:<24} {val}")
    samples = sub.get("samples") or []
    if samples:
        click.echo(f"  {'Samples':<24} {len(samples)}")
        for s in samples:
            click.echo(
                f"    - {s.get('sample_id')!s:<20} "
                f"{s.get('per_sample_status') or '—'}"
            )


@submissions.command("update")
@click.argument("submission_id", type=int)
@click.option("--title", default=None)
@click.option("--description", default=None)
@click.option("--release-date", default=None)
@click.option("--bioproject", "bioproject_accession", default=None)
@click.option(
    "--target-repo",
    "target_repository",
    default=None,
    type=click.Choice(
        [
            "NCBI",
            "GISAID_EPICOV",
            "GISAID_EPIFLU",
            "GISAID_EPIPOX",
            "ENA",
            "DDBJ",
        ],
        case_sensitive=False,
    ),
)
def submissions_update(
    submission_id: int,
    title: str | None,
    description: str | None,
    release_date: str | None,
    bioproject_accession: str | None,
    target_repository: str | None,
) -> None:
    """Patch updatable fields on a submission."""
    fields: dict = {}
    if title is not None:
        fields["title"] = title
    if description is not None:
        fields["description"] = description
    if release_date is not None:
        fields["release_date"] = release_date
    if bioproject_accession is not None:
        fields["bioproject_accession"] = bioproject_accession
    if target_repository is not None:
        fields["target_repository"] = target_repository.upper()
    if not fields:
        click.echo("No fields to update — pass at least one option.", err=True)
        raise SystemExit(2)
    try:
        sub = _module().update(submission_id, **fields)
    except Exception as exc:
        _handle_error(exc, "Update submission")
        return
    click.echo(f"Updated submission {sub.get('id')}.")


@submissions.command("delete")
@click.argument("submission_id", type=int)
@click.option("--yes", is_flag=True, default=False, help="Skip confirmation prompt.")
def submissions_delete(submission_id: int, yes: bool) -> None:
    """Soft-delete a submission."""
    if not yes and not click.confirm(
        f"Soft-delete submission {submission_id}?", default=False
    ):
        click.echo("Aborted.")
        return
    try:
        _module().delete(submission_id)
    except Exception as exc:
        _handle_error(exc, "Delete submission")
        return
    click.echo(f"Deleted submission {submission_id}.")


# ── samples + validation + package ───────────────────────────────────


def _parse_sample_ids(raw: tuple[str, ...]) -> list[int]:
    out: list[int] = []
    for r in raw:
        for piece in r.split(","):
            piece = piece.strip()
            if not piece:
                continue
            try:
                out.append(int(piece))
            except ValueError:
                click.echo(f"Invalid sample ID {piece!r}.", err=True)
                raise SystemExit(2) from None
    return out


@submissions.command("add-samples")
@click.argument("submission_id", type=int)
@click.option("--samples", "sample_ids_str", required=True, multiple=True)
def submissions_add_samples(submission_id: int, sample_ids_str: tuple[str, ...]) -> None:
    """Attach samples to a DRAFT submission."""
    sample_ids = _parse_sample_ids(sample_ids_str)
    try:
        result = _module().add_samples(submission_id, sample_ids)
    except Exception as exc:
        _handle_error(exc, "Add samples")
        return
    click.echo(f"Added {result.get('added', len(sample_ids))} sample(s).")


@submissions.command("remove-samples")
@click.argument("submission_id", type=int)
@click.option("--samples", "sample_ids_str", required=True, multiple=True)
def submissions_remove_samples(
    submission_id: int, sample_ids_str: tuple[str, ...]
) -> None:
    """Detach samples from a DRAFT submission."""
    sample_ids = _parse_sample_ids(sample_ids_str)
    try:
        result = _module().remove_samples(submission_id, sample_ids)
    except Exception as exc:
        _handle_error(exc, "Remove samples")
        return
    click.echo(f"Removed {result.get('removed', 0)} sample(s).")


@submissions.command("validate")
@click.argument("submission_id", type=int)
@click.option("--json", "output_json", is_flag=True, default=False)
def submissions_validate(submission_id: int, output_json: bool) -> None:
    """Validate readiness of all attached samples."""
    try:
        result = _module().validate(submission_id)
    except Exception as exc:
        _handle_error(exc, "Validate submission")
        return
    if output_json:
        _print_json(result)
        return
    if result.get("valid"):
        click.echo("All samples pass readiness validation.")
        return
    issues = result.get("per_sample") or []
    click.echo(f"{len(issues)} sample(s) have issues:")
    for ps in issues:
        click.echo(f"  - {ps.get('sample_id')}:")
        for issue in ps.get("issues", []):
            click.echo(f"      • {issue}")


@submissions.command("generate")
@click.argument("submission_id", type=int)
@click.option(
    "--copy-files",
    is_flag=True,
    default=False,
    help="Copy referenced files into the package instead of linking.",
)
def submissions_generate(submission_id: int, copy_files: bool) -> None:
    """Generate the on-disk package for the submission."""
    try:
        result = _module().generate(submission_id, copy_files=copy_files)
    except Exception as exc:
        _handle_error(exc, "Generate package")
        return
    click.echo(f"Package generated at: {result.get('package_path')}")


@submissions.command("mark-submitted")
@click.argument("submission_id", type=int)
def submissions_mark_submitted(submission_id: int) -> None:
    """Mark the submission as submitted (after running Seqsender manually)."""
    try:
        sub = _module().mark_submitted(submission_id)
    except Exception as exc:
        _handle_error(exc, "Mark submitted")
        return
    click.echo(f"Marked submission {sub.get('id')} as SUBMITTED.")


@submissions.command("register-accessions")
@click.argument("submission_id", type=int)
@click.option(
    "--accessions-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="JSON file with an 'accessions' array.",
)
@click.option(
    "--accessions",
    "accessions_json",
    default=None,
    help="Inline JSON array of accession entries.",
)
def submissions_register_accessions(
    submission_id: int,
    accessions_file: Path | None,
    accessions_json: str | None,
) -> None:
    """Record accessions returned by the repository."""
    if accessions_file:
        try:
            data = _json.loads(accessions_file.read_text(encoding="utf-8"))
        except Exception as exc:
            click.echo(f"Could not read {accessions_file}: {exc}", err=True)
            raise SystemExit(2) from None
        accessions = data.get("accessions") if isinstance(data, dict) else data
    elif accessions_json:
        try:
            accessions = _json.loads(accessions_json)
        except Exception as exc:
            click.echo(f"Could not parse --accessions JSON: {exc}", err=True)
            raise SystemExit(2) from None
    else:
        click.echo(
            "Provide either --accessions-file or --accessions JSON.", err=True
        )
        raise SystemExit(2)
    if not isinstance(accessions, list):
        click.echo("Accessions payload must be a list of entries.", err=True)
        raise SystemExit(2)
    try:
        result = _module().register_accessions(submission_id, accessions)
    except Exception as exc:
        _handle_error(exc, "Register accessions")
        return
    click.echo(f"Registered {len(accessions)} accession(s); status={result.get('status')}")


@submissions.command("mark-rejected")
@click.argument("submission_id", type=int)
@click.option("--reason", required=True, help="Why the repository rejected the submission.")
def submissions_mark_rejected(submission_id: int, reason: str) -> None:
    """Record that the repository rejected this submission."""
    try:
        sub = _module().mark_rejected(submission_id, reason)
    except Exception as exc:
        _handle_error(exc, "Mark rejected")
        return
    click.echo(f"Marked submission {sub.get('id')} as REJECTED.")


@submissions.command("withdraw")
@click.argument("submission_id", type=int)
@click.option("--reason", required=True, help="Why the submission is being withdrawn.")
def submissions_withdraw(submission_id: int, reason: str) -> None:
    """Withdraw a previously submitted submission."""
    try:
        sub = _module().withdraw(submission_id, reason)
    except Exception as exc:
        _handle_error(exc, "Withdraw submission")
        return
    click.echo(f"Withdrew submission {sub.get('id')}.")


# ── I-3c: backend execution ──────────────────────────────────────────


@submissions.command("execute")
@click.argument("submission_id", type=int)
def submissions_execute(submission_id: int) -> None:
    """Queue this submission for backend (Seqsender) execution.

    The deployment must have ``allow_backend_submission=True`` and the
    target repo enabled in ``backend_submission_repos``. Required
    credentials must be configured via the C-1 abstraction.
    """
    try:
        sub = _module().execute(submission_id)
    except Exception as exc:
        _handle_error(exc, "Execute submission")
        return
    click.echo(f"Submission {sub.get('id')} queued for backend execution.")
    click.echo(f"  Status: {sub.get('status')}")
    click.echo(f"  Attempt: {sub.get('execution_attempt_count')}")
    click.echo(
        "  Run `jackpot submissions show {sid}` to check status, or "
        "`jackpot submissions execution-logs {sid}` to view per-attempt "
        "logs.".format(sid=sub.get("id"))
    )


@submissions.command("retry-execution")
@click.argument("submission_id", type=int)
def submissions_retry_execution(submission_id: int) -> None:
    """Re-queue a failed or interrupted submission for backend execution."""
    try:
        sub = _module().retry_execution(submission_id)
    except Exception as exc:
        _handle_error(exc, "Retry execution")
        return
    click.echo(f"Submission {sub.get('id')} re-queued for backend execution.")
    click.echo(f"  Status: {sub.get('status')}")
    click.echo(f"  Attempt: {sub.get('execution_attempt_count')}")


@submissions.command("execution-logs")
@click.argument("submission_id", type=int)
@click.option("--json", "output_json", is_flag=True, default=False)
def submissions_execution_logs(submission_id: int, output_json: bool) -> None:
    """List per-attempt execution-log entries for the submission."""
    try:
        entries = _module().execution_logs(submission_id)
    except Exception as exc:
        _handle_error(exc, "Fetch execution logs")
        return
    if output_json:
        _print_json(entries)
        return
    if not entries:
        click.echo("No execution attempts yet.")
        return
    for entry in entries:
        attempt = entry.get("attempt")
        status = entry.get("exit_status") or "—"
        click.echo(f"  Attempt {attempt}: status={status}")
        log_view = entry.get("log_view_url") or entry.get("log_uri") or "—"
        click.echo(f"    Log: {log_view}")
