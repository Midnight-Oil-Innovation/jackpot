"""
jackpot.cli.samples
~~~~~~~~~~~~~~~~~~~
`jackpot samples` command group.

Commands:
  jackpot samples list    — list samples in a project
  jackpot samples get     — get a single sample
  jackpot samples search  — search across all visible samples
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
def samples() -> None:
    """Query and manage samples."""


@samples.command("list")
@click.option("--project", type=int, default=None, help="Filter by project ID")
@click.option("--lab", type=int, default=None, help="Filter by lab ID")
@click.option(
    "--status",
    default=None,
    type=click.Choice(
        ["PRELIMINARY", "ANALYZABLE", "SUBMITTABLE", "QC_FAILED", "UNDER_REVIEW", "RETRACTED"]
    ),
    help="Filter by quality_status (metadata tier)",
)
@click.option("--organism", default=None, help="Filter by organism name")
@click.option(
    "--sector",
    default=None,
    type=click.Choice(
        [
            "clinical",
            "veterinary",
            "agricultural",
            "environmental",
            "wastewater",
            "wildlife",
            "research",
        ]
    ),
)
@click.option(
    "--surveillance-relevant",
    is_flag=True,
    default=False,
    help="Show only surveillance-relevant samples",
)
@click.option("--page", type=int, default=1, help="Page number")
@click.option("--per-page", type=int, default=50, help="Results per page (max 200)")
@click.option(
    "--json", "output_json", is_flag=True, default=False, help="Output as JSON instead of a table"
)
def samples_list(
    project: int | None,
    lab: int | None,
    status: str | None,
    organism: str | None,
    sector: str | None,
    surveillance_relevant: bool,
    page: int,
    per_page: int,
    output_json: bool,
) -> None:
    """List samples.

    \b
    Examples:
      jackpot samples list --project 42
      jackpot samples list --project 42 --status PRELIMINARY
      jackpot samples list --organism "Salmonella enterica" --sector clinical
    """
    client = _get_client()

    params: dict = {"page": page, "per_page": per_page}
    if project:
        params["project_id"] = project
    if lab:
        params["lab_id"] = lab
    if status:
        params["quality_status"] = status
    if organism:
        params["organism_name"] = organism
    if sector:
        params["sector"] = sector
    if surveillance_relevant:
        params["surveillance_relevant"] = True

    try:
        # TODO: implement when GET /api/v1/samples/ is built
        response = client.get("/api/v1/samples/", params=params)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    if output_json:
        import json

        click.echo(json.dumps(response, indent=2))
        return

    # Render as table
    items = response if isinstance(response, list) else response.get("data", [])
    if not items:
        click.echo("No samples found.")
        return

    table = Table(title=f"Samples (page {page})")
    table.add_column("sample_id", style="cyan")
    table.add_column("organism")
    table.add_column("sector")
    table.add_column("tier", style="green")
    table.add_column("scrub")
    table.add_column("date_collected")
    table.add_column("surv.")

    for s in items:
        table.add_row(
            s.get("sample_id", ""),
            s.get("organism_name", ""),
            s.get("sector", ""),
            s.get("quality_status", ""),
            s.get("scrub_status", ""),
            s.get("date_collected", ""),
            "✓" if s.get("surveillance_relevant") else "—",
        )

    console.print(table)


@samples.command("get")
@click.argument("sample_id")
@click.option("--json", "output_json", is_flag=True, default=False, help="Output as JSON")
def samples_get(sample_id: str, output_json: bool) -> None:
    """Get a single sample by ID.

    \b
    Example:
      jackpot samples get AZ-2026-001
    """
    client = _get_client()

    try:
        # TODO: implement when GET /api/v1/samples/{sample_id} is built
        result = client.get(f"/api/v1/samples/{sample_id}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    if output_json:
        import json

        click.echo(json.dumps(result, indent=2))
        return

    # Pretty-print key fields
    for key, label in [
        ("sample_id", "Sample ID"),
        ("organism_name", "Organism"),
        ("source_type", "Source type"),
        ("sector", "Sector"),
        ("quality_status", "Quality tier"),
        ("scrub_status", "Scrub status"),
        ("surveillance_relevant", "Surveillance relevant"),
        ("date_collected", "Date collected"),
        ("date_collected_precision", "Date precision"),
        ("collection_location_country", "Country"),
        ("collection_location_state", "State/Region"),
        ("collection_location_city", "City"),
        ("sharing_level", "Sharing level"),
        ("project_id", "Project"),
        ("lab_id", "Lab"),
    ]:
        val = result.get(key)
        if val is not None:
            click.echo(f"  {label:<30} {val}")


@samples.command("search")
@click.option("--query", required=True, help="Search query (organism, sample_id, etc.)")
@click.option("--project", type=int, default=None)
@click.option("--page", type=int, default=1)
@click.option("--json", "output_json", is_flag=True, default=False)
def samples_search(
    query: str,
    project: int | None,
    page: int,
    output_json: bool,
) -> None:
    """Search samples across all visible projects.

    \b
    Example:
      jackpot samples search --query "Salmonella"
      jackpot samples search --query "AZ-2026" --project 42
    """
    client = _get_client()

    params: dict = {"q": query, "page": page, "per_page": 50}
    if project:
        params["project_id"] = project

    try:
        # TODO: implement when GET /api/v1/samples/ supports free-text search
        response = client.get("/api/v1/samples/", params=params)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    if output_json:
        import json

        click.echo(json.dumps(response, indent=2))
        return

    items = response if isinstance(response, list) else response.get("data", [])
    if not items:
        click.echo(f"No samples found matching '{query}'.")
        return

    click.echo(f"Found {len(items)} samples matching '{query}':")
    for s in items:
        click.echo(
            f"  {s.get('sample_id'):<20} "
            f"{s.get('organism_name', ''):<35} "
            f"[{s.get('quality_status', '')}]"
        )
