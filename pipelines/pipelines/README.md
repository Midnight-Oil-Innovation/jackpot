# Pipeline wrappers

Per-pipeline directories land here in Sessions J-M:

- Session J: `cecret/`, `viralrecon/`, `walkercreek/`
- Session K: `bactopia/`, `grandeur/`, `mycosnp-nf/`, `tb-profiler/`
- Session L: `mag/`, `taxprofiler/`
- Session M: `pathogensurveillance/`

Each wrapper directory contains:

- `jackpot_wrapper.nf` — runs the upstream pipeline, then invokes parsers
- `parsers/*.py` — per-output-file parsers emitting `ParsedResult` objects
- `SUPPORTED_PIPELINE_VERSIONS` — semver range declaration
