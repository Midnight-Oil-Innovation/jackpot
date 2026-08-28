> **Status:** History — point-in-time Apptainer audit of the pipeline-zoo wrappers (P0h H-2). Point-in-time record.

# Pipeline-zoo Apptainer audit (P0h H-2)

H-2 audits the ten pipeline wrappers under `pipelines/pipelines/` for
Apptainer compatibility and lays the foundation for pre-staging OCI
images on air-gapped clusters.

## Findings — short version

- The container-engine selection is rendered by JACKPOT, not by the
  per-pipeline wrapper. `base.config.j2` (P0g G-3) emits `apptainer {
  enabled = true; autoMounts = true; cacheDir = ... }` whenever the
  active execution profile has `container_engine = APPTAINER`. None of
  the wrappers override or fight that.
- Every wrapper that integrates with JACKPOT runs a Python REGISTER
  process (`label 'jackpot_register'`), so every cluster needs a
  Python container in addition to the upstream pipeline's container
  set.
- Per-process upstream BioContainer images are not enumerated in this
  PR. Each pipeline's `apptainer_images.txt` declares the upstream
  slug + config URL; a future `jackpot images audit <pipeline>` CLI
  will parse the upstream `conf/modules.config` and emit the full
  per-process list. For nf-core pipelines, the off-the-shelf path is
  `nf-core download <name> --container singularity --outdir <cache>`
  and that is the recommendation in the per-manifest `@audit-note`.

## What this PR ships

A manifest format + reader + per-pipeline manifests, structured so a
follow-up CLI can extend the lists without touching the reader.

- `pipelines/pipelines/apptainer_manifest.py` — the canonical reader
  for `apptainer_images.txt`. Defines :class:`ApptainerManifest`,
  :func:`parse_manifest_text`, :func:`load_manifest`, and
  :func:`list_pipelines_with_manifests`.
- `pipelines/pipelines/<name>/apptainer_images.txt` — one per
  pipeline. UTF-8, line-oriented; one OCI URI per line, `#` comments
  allowed, `@directive value` metadata lines tolerated. Today the
  shipped images are the JACKPOT register-process Python container
  and a `@audit-status partial` directive declaring the upstream slug
  for the future audit CLI.
- `pipelines/tests/test_apptainer_manifest.py` — 16 tests covering
  the parser contract, the loader, and an in-tree sweep that asserts
  every shipped pipeline has a parseable manifest declaring
  `@upstream` and including a Python container.

## Per-pipeline status

For each pipeline below, "audit status" means "what fraction of the
runtime container set is enumerated in this repo's manifest." `partial`
is the universal status today: every pipeline declares the upstream
slug + the JACKPOT register container; the upstream BioContainer set
is deferred to a follow-up CLI.

- `bactopia` — upstream `bactopia/bactopia`. Pre-stage path:
  `bactopia build --pull` against the deployment's container cache.
- `cecret` — upstream `UPHL-BioNGS/Cecret`. Per-process containers
  declared inline in the upstream `nextflow.config`.
- `grandeur` — upstream `UPHL-BioNGS/Grandeur`. Per-process
  containers (AMRFinderPlus, Tseemann mlst, Kraken2, BLAST) declared
  upstream.
- `mag` — upstream `nf-core/mag`. nf-core BioContainer set;
  pre-stage via `nf-core download mag --container singularity
  --outdir <cache>`.
- `mycosnp` — upstream `CDCgov/mycosnp-nf`. Per-process containers
  declared in upstream `nextflow.config`.
- `pathogensurveillance` — upstream `nf-core/pathogensurveillance` at
  pinned version `1.1.0`. Eight result surfaces, each backed by its
  own BioContainer.
- `taxprofiler` — upstream `nf-core/taxprofiler`. Multi-classifier
  BioContainer set.
- `tb_profiler` — upstream `jodyphelan/tbprofiler-nf`. Single-tool;
  the upstream config pins
  `quay.io/biocontainers/tb-profiler:<ver>--<hash>` per supported
  version.
- `viralrecon` — upstream `nf-core/viralrecon`. nf-core BioContainer
  set per the upstream `conf/modules.config`.
- `walkercreek` — upstream `UPHL-BioNGS/walkercreek`. IRMA + per-
  segment subtype calls; per-process containers upstream.

## Recommended pre-staging procedure (operator workflow)

For each pipeline an operator intends to run on an air-gapped
Apptainer cluster:

1. Read the manifest with `python -m pipelines.apptainer_manifest`
   (a thin CLI wrapper is a follow-up; for now, read the file
   directly or import the module).
2. For nf-core pipelines, run `nf-core download <name> --container
   singularity --outdir <cache>` against an internet-connected host;
   copy the resulting `.sif` set into the cluster's Apptainer cache.
3. For non-nf-core pipelines (Cecret / Grandeur / mycosnp / bactopia
   / walkercreek / tb-profiler), pull each container declared in the
   upstream config to a `.sif` and copy into the cache.
4. Pull the JACKPOT register-process Python container
   (`docker.io/library/python:3.12-slim-bookworm`) into the same
   cache. JACKPOT uses this for the per-run `REGISTER_RESULTS`
   process on every wrapper.
5. Set the JACKPOT execution profile's
   `config_overrides.apptainer_cache_dir` to point at the cache, so
   `base.config.j2`'s `apptainer { cacheDir = ... }` line
   resolves to the staged location at every launch.

`jackpot images export <pipeline>` and `jackpot images audit
<pipeline>` are CLI follow-ups that automate steps 2–4.

## Out of scope for H-2

- Full per-process BioContainer enumeration — each upstream's
  `conf/modules.config` would need parsing, and that is the future
  `jackpot images audit` CLI's job.
- Pre-pulling and bundling SIF files — that's the future `jackpot
  images export` CLI.
- Profile-level per-pipeline overrides (e.g. "force `viralrecon` to
  use `singularity` even when the profile says `apptainer`"). The
  current model is profile-wide.

## Cross-references

- `pipelines/pipelines/apptainer_manifest.py` — reader API
- `backend/backend/pipeline_config/profile_templates/base.config.j2`
  — where the rendered config emits the `apptainer { ... }` block
  and consumes `config_overrides.apptainer_cache_dir`
- `todo.md` lines 1697–1850 — the full P0h spec; H-2 is one of ten
  blocks landing in the campaign.
