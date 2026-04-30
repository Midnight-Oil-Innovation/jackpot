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

## Parser version matrix

Every wrapper package declares a `SUPPORTED_PIPELINE_VERSIONS` list
in `pipelines/<name>/parsers/__init__.py`. The launcher calls
`shared.version_check.check_pipeline_version(...)` at run start and
emits a `pipeline_events` warning (non-blocking) when the requested
upstream version is not in the list.  Bump `parser_version` in
`pipeline_catalog` whenever a parser's output shape changes — it is
the signal consumers use to decide whether historical runs are
field-for-field comparable.

| Wrapper                | Upstream                          | Parser version | Supported pipeline versions |
| ---------------------- | --------------------------------- | -------------- | --------------------------- |
| `cecret`               | UPHL-BioNGS/Cecret                | 0.1.0          | 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15, 3.16, 3.20, 3.30, 3.40, 3.50, 3.60, 3.66 |
| `viralrecon`           | nf-core/viralrecon                | 0.1.0          | 2.5, 2.6, 2.6.0, 2.6.1, 2.7, 2.7.0 |
| `walkercreek`          | UPHL-BioNGS/walkercreek           | 0.1.0          | 1.0, 1.1, 1.1.4, 1.2        |
| `bactopia`             | bactopia/bactopia                 | 0.1.0          | 2.2.0, 3.0.0, 3.0.1, 3.1.0  |
| `grandeur`             | UPHL-BioNGS/Grandeur              | 0.1.0          | 3.2.0, 3.3.0, 4.0.0, 4.1.0, 4.2.0 |
| `mycosnp`              | CDCgov/mycosnp-nf                 | 0.1.0          | 1.5, 1.6, 2.0, 2.1          |
| `tb_profiler`          | jodyphelan/tb-profiler            | 0.1.0          | 5.0.0, 6.0.0, 6.1.0, 6.2.0  |
| `mag`                  | nf-core/mag                       | 0.1.0          | 2.5.4, 3.0.0, 3.0.3, 3.1.0  |
| `taxprofiler`          | nf-core/taxprofiler               | 0.1.0          | 1.1.5, 1.1.6, 1.2.0         |
| `pathogensurveillance` | nf-core/pathogensurveillance      | 0.1.0          | 1.1.0                       |

All parser versions start at `0.1.0` for the Month 2 rollout and
are bumped according to:

- `0.x.Y` — bugfix that does not change payload field names or types
- `0.X.0` — additive change (new fields, new result types)
- `1.0.0` — first stable release after Month 3 hardening

Any breaking change to a payload (rename, type change, removed
field) is a major bump and requires a matching Alembic migration
on the consumer tables.

## Development

Install dev deps:

```bash
uv sync
uv run pytest
```
