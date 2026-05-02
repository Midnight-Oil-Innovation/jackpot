"""
jackpot.cli.pipelines
~~~~~~~~~~~~~~~~~~~~~
`jackpot pipelines` command group.

Commands:
  jackpot pipelines list    — list pipeline runs for a project
  jackpot pipelines launch  — launch a pipeline
  jackpot pipelines status  — get status of a specific run
  jackpot pipelines cancel  — cancel a running pipeline
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from jackpot.cli.config import get_client_credentials
from jackpot.core.client import JACKPOTClient
from jackpot.core.exceptions import ConfigError

console = Console()


def _get_client() -> JACKPOTClient:
    try:
        api_url, token = get_client_credentials()
        return JACKPOTClient(api_url=api_url, token=token)
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@click.group()
def pipelines() -> None:
    """Launch and monitor pipelines."""


@pipelines.command("list")
@click.option("--project", type=int, default=None, help="Filter by project ID")
@click.option(
    "--status",
    default=None,
    type=click.Choice(["queued", "submitted", "running", "completed", "failed", "aborted"]),
    help="Filter by run status",
)
@click.option("--page", type=int, default=1)
@click.option("--json", "output_json", is_flag=True, default=False)
def pipelines_list(
    project: int | None,
    status: str | None,
    page: int,
    output_json: bool,
) -> None:
    """List pipeline runs.

    \b
    Example:
      jackpot pipelines list --project 42
      jackpot pipelines list --status failed
    """
    client = _get_client()

    params: dict = {"page": page, "per_page": 50}
    if project:
        params["project_id"] = project
    if status:
        params["status"] = status

    try:
        response = client.get("/api/v1/pipelines/", params=params)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    if output_json:
        import json

        click.echo(json.dumps(response, indent=2))
        return

    items = response if isinstance(response, list) else response.get("data", [])
    if not items:
        click.echo("No pipeline runs found.")
        return

    table = Table(title="Pipeline runs")
    table.add_column("run_id", style="cyan")
    table.add_column("pipeline")
    table.add_column("version")
    table.add_column("status")
    table.add_column("samples")
    table.add_column("started")
    table.add_column("duration")

    for r in items:
        table.add_row(
            str(r.get("id", "")),
            r.get("pipeline_name", ""),
            r.get("pipeline_version", ""),
            r.get("status", ""),
            str(r.get("sample_count", "")),
            r.get("started_at", ""),
            r.get("duration", ""),
        )

    console.print(table)


@pipelines.command("launch")
@click.option(
    "--pipeline", required=True, help="Pipeline name (e.g. 'nf-core/viralrecon', 'GHRU assembly')"
)
@click.option(
    "--project",
    type=int,
    default=None,
    help="Project ID (uses JACKPOT_PROJECT_ID env var if not set)",
)
@click.option(
    "--samples", default=None, help="Comma-separated sample IDs (omit to use all project samples)"
)
@click.option("--version", default=None, help="Pipeline version/revision (default: latest)")
@click.option("--params", default=None, help="Pipeline parameters as JSON string")
@click.option("--wait", is_flag=True, default=False, help="Block until pipeline completes")
def pipelines_launch(
    pipeline: str,
    project: int | None,
    samples: str | None,
    version: str | None,
    params: str | None,
    wait: bool,
) -> None:
    """Launch a pipeline on project samples.

    \b
    Examples:
      # Launch on all project samples
      jackpot pipelines launch \\
          --pipeline "nf-core/viralrecon" \\
          --project 42

      # Launch on specific samples with custom params
      jackpot pipelines launch \\
          --pipeline "nf-core/viralrecon" \\
          --project 42 \\
          --samples "AZ-001,AZ-002,AZ-003" \\
          --params '{"genome": "MN908947.3", "protocol": "amplicon"}'

      # Launch and wait for completion
      jackpot pipelines launch \\
          --pipeline "GHRU assembly" \\
          --project 42 \\
          --wait
    """
    import json as _json

    client = _get_client()

    # Parse params JSON
    params_dict: dict = {}
    if params:
        try:
            params_dict = _json.loads(params)
        except _json.JSONDecodeError as e:
            raise click.UsageError(f"--params must be valid JSON: {e}")

    # Parse sample IDs
    sample_ids = [s.strip() for s in samples.split(",")] if samples else None

    payload: dict = {"pipeline": pipeline}
    if project:
        payload["project_id"] = project
    if sample_ids:
        payload["sample_ids"] = sample_ids
    if version:
        payload["version"] = version
    if params_dict:
        payload["params"] = params_dict

    click.echo(f"Launching {pipeline}...")

    try:
        result = client.post("/api/v1/pipelines/launch", json=payload)
        run_id = result.get("id")
        click.echo(f"Pipeline run started: run_id={run_id}")
        click.echo(f"Status: {result.get('status', 'queued')}")
        click.echo(f"Monitor: jackpot pipelines status {run_id}")
    except Exception as e:
        click.echo(f"Launch failed: {e}", err=True)
        raise SystemExit(1)


@pipelines.command("status")
@click.argument("run_id", type=int)
@click.option("--tasks", is_flag=True, default=False, help="Show per-task breakdown")
@click.option("--json", "output_json", is_flag=True, default=False)
def pipelines_status(run_id: int, tasks: bool, output_json: bool) -> None:
    """Get the status of a pipeline run.

    \b
    Example:
      jackpot pipelines status 123
      jackpot pipelines status 123 --tasks
    """
    client = _get_client()

    try:
        result = client.get(f"/api/v1/pipelines/{run_id}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    if output_json:
        import json

        click.echo(json.dumps(result, indent=2))
        return

    click.echo(f"Run ID:    {result.get('id')}")
    click.echo(f"Pipeline:  {result.get('pipeline_name')} {result.get('pipeline_version', '')}")
    click.echo(f"Status:    {result.get('status')}")
    click.echo(f"Samples:   {result.get('sample_count')}")
    click.echo(f"Started:   {result.get('started_at', 'not yet')}")
    click.echo(f"Work dir:  {result.get('work_dir', 'not set')}")

    if tasks:
        try:
            task_list = client.get(f"/api/v1/pipelines/{run_id}/tasks")
            click.echo(f"\nTasks ({len(task_list)}):")
            for t in task_list:
                status_icon = {
                    "COMPLETED": "✓",
                    "FAILED": "✗",
                    "CACHED": "↩",
                    "RUNNING": "⟳",
                }.get(t.get("status", ""), "?")
                click.echo(
                    f"  {status_icon} {t.get('process_name', ''):<50} "
                    f"{t.get('wall_time_seconds', 0):.0f}s  "
                    f"{t.get('peak_memory_mb', 0):.0f}MB"
                )
        except Exception as e:
            click.echo(f"Could not fetch tasks: {e}", err=True)


@pipelines.command("cancel")
@click.argument("run_id", type=int)
@click.confirmation_option(prompt="Cancel this pipeline run?")
def pipelines_cancel(run_id: int) -> None:
    """Cancel a running pipeline.

    \b
    Example:
      jackpot pipelines cancel 123
    """
    client = _get_client()

    try:
        # TODO: implement when POST /api/v1/pipelines/{run_id}/cancel is built
        result = client.post(f"/api/v1/pipelines/{run_id}/cancel")
        click.echo(f"Run {run_id} cancelled.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
