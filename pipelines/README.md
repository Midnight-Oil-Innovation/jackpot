# jackpot-nf

Nextflow plugin, pipeline wrappers, and shared Python parsers for the JACKPOT
pathogen genomics platform.

This repo is a git submodule of `jackpot-backend` mounted at `nf/` and is
the single source of truth for:

- The `nf-jackpot` Nextflow plugin — generic weblog and workdir handling
- Per-pipeline wrappers that run an upstream pipeline (Cecret, viralrecon,
  walkercreek, bactopia, Grandeur, mycosnp, tb-profiler, nf-core/mag,
  nf-core/taxprofiler, nf-core/pathogensurveillance) and parse the outputs
- The shared `jackpot_register_client` HTTP client used by every parser
  to POST typed results back to the JACKPOT API
- The shared `hamronization_normalizer` wrapper around the hAMRonization tool
- The Pydantic result payload schemas that the JACKPOT API validates against

## Layout

```
jackpot-nf/
├── plugins/nf-jackpot/       # Nextflow plugin
├── pipelines/                # Per-pipeline wrapper directories (Sessions J-M)
├── shared/
│   ├── jackpot_register_client.py
│   ├── hamronization_normalizer.py
│   └── schemas/              # Pydantic result payloads
├── tests/
│   └── fixtures/             # Real pipeline outputs per pipeline
├── pyproject.toml
└── README.md
```

## Registration protocol

1. Pipeline wrapper runs the upstream pipeline
2. Wrapper calls `parse(output_dir)` on the matching parser
3. For each `ParsedResult`, the wrapper calls
   `jackpot_register_client.register_result(result_type, payload)`
4. The client POSTs to
   `/api/v1/pipelines/{run_id}/results/{result_type}` with the
   `X-Pipeline-Token` header matching `pipeline_runs.pipeline_token`
5. The API validates the payload against the Pydantic schema for that
   `result_type` and writes to the typed table in the same transaction
   as a `pipeline_results.metrics` JSONB merge

## Environment variables

The register client reads these at parser runtime:

- `JACKPOT_API_URL` — e.g. `https://api.jackpot.example.com`
- `JACKPOT_RUN_ID` — the run's external `run_id`
- `JACKPOT_PIPELINE_TOKEN` — the per-run secret stored on `pipeline_runs`

## Development

Install dev deps:

```bash
uv sync
uv run pytest
```
