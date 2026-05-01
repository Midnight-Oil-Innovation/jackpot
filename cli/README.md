# jackpot-cli

Command-line interface and Python SDK for the JACKPOT pathogen genomics platform.

## Overview

This repo provides two things in a single package:

**jackpot-sdk** — A Python package for programmatic access to JACKPOT from
Jupyter notebooks, workspace pods, and analysis scripts. Pre-installed in
all JACKPOT workspace profiles (Analyst, Bioinformatician, Developer).

**jackpot-cli** — A command-line tool for uploading samples, launching
pipelines, and querying samples from the terminal or bash scripts.

## Installation

```bash
pip install jackpot
```

Or with uv (recommended):
```bash
uv pip install jackpot
```

## CLI Quick Start

```bash
# One-time setup
jackpot config set --api-url https://api.your-jackpot-instance.org
jackpot auth login   # opens browser for Google OAuth, stores 1-year token

# Upload a single sample
jackpot upload \
    --r1 EX-2026-001_R1.fastq.gz \
    --r2 EX-2026-001_R2.fastq.gz \
    --organism "Salmonella enterica" \
    --source-type isolate \
    --sector clinical \
    --project 42 \
    --date-collected 2026-04-01

# Bulk upload a directory
jackpot upload-dir /data/sequences/ \
    --metadata-csv /data/sequences/metadata.csv \
    --project 42

# Upload via Globus (large batches from HPC)
jackpot upload-globus \
    --metadata-csv metadata.csv \
    --source-endpoint your-hpc-cluster \
    --source-path /your/sequencing/data/path/ \
    --project 42

# List samples in a project
jackpot samples list --project 42 --status PRELIMINARY

# Launch a pipeline
jackpot pipelines launch \
    --pipeline nf-core/viralrecon \
    --project 42
```

## SDK Quick Start

```python
from jackpot import Session

# Picks up JACKPOT_API_URL and JACKPOT_API_TOKEN env vars automatically
# (pre-set in all JACKPOT workspace pods via context injection)
session = Session()

# Search samples
df = session.samples.search(
    organism="Salmonella enterica",
    date_range=("2025-01-01", "2026-01-01"),
    sector="clinical",
    quality_status="ANALYZABLE",
)

# Download a FASTQ
sample = session.samples.get("EX-2026-001")
r1_path = sample.download_fastq(r1=True)

# Launch a pipeline
run = session.pipelines.launch(
    "nf-core/viralrecon",
    sample_ids=df["sample_id"].tolist(),
    params={"genome": "MN908947.3", "protocol": "amplicon"},
)
run.wait(poll_interval=30)
results = run.results()

# Register notebook outputs back to JACKPOT
session.datasets.register_from_notebook(
    name="SARS-CoV-2 Q1 2026 analysis",
    sample_ids=df["sample_id"].tolist(),
    sharing_level="LAB",
)
```

## Architecture

```
jackpot/
├── core/
│   ├── client.py       HTTP client (httpx) — all API calls go here
│   └── exceptions.py   JACKPOTError, AuthError, NotFoundError, etc.
├── sdk/
│   ├── session.py      Session — entry point for all SDK usage
│   ├── samples.py      SamplesModule — search, get, download
│   ├── pipelines.py    PipelinesModule — launch, wait, results
│   ├── datasets.py     DatasetsModule — create, register_from_notebook
│   ├── sra.py          SRAModule — fetch SRA accessions to workspace
│   ├── references.py   ReferencesModule — download reference genomes
│   └── workspace.py    WorkspaceModule — add_package, workspace utilities
└── cli/
    ├── main.py         Click CLI entry point — `jackpot` command
    ├── config.py       ~/.jackpot/config.toml management
    ├── auth.py         `jackpot auth` commands
    ├── upload.py       `jackpot upload*` commands
    ├── samples.py      `jackpot samples` commands
    └── pipelines.py    `jackpot pipelines` commands
```

## Token Storage

API tokens are stored in `~/.jackpot/config.toml`:

```toml
[default]
api_url = "https://api.your-jackpot-instance.org"
token = "jk_live_..."
token_expires = "2027-04-09T00:00:00Z"
```

Default token lifetime: 1 year. Revoke tokens at any time via the JACKPOT
platform admin UI or `jackpot auth revoke`.

## Environment Variables

The SDK checks these environment variables before falling back to the config file:

| Variable | Description |
|---|---|
| `JACKPOT_API_URL` | JACKPOT API base URL |
| `JACKPOT_API_TOKEN` | API token (pre-set in workspace pods) |
| `JACKPOT_PROJECT_ID` | Default project ID (pre-set in workspace pods) |
| `JACKPOT_LAB_ID` | Default lab ID (pre-set in workspace pods) |

## Development

```bash
git clone git@github.com:gotero/jackpot-cli.git
cd jackpot-cli
uv sync --extra dev
uv run pytest
```
