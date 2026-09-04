# Pipeline wrappers

One directory per upstream pipeline. Ten exist today: `bactopia`,
`cecret`, `grandeur`, `mag`, `mycosnp`, `pathogensurveillance`,
`taxprofiler`, `tb_profiler`, `viralrecon`, `walkercreek`.

## What every wrapper has

- `parsers/` — a **package**, not a single module. `parsers/__init__.py`
  is the pipeline-level entry point and the per-output-file parsers sit
  beside it (`snippy.py`, `tree.py`, `typing.py`, …). It exports three
  names, and `pipelines/tests/` loads them by that contract:

  | Name | Shape |
  |---|---|
  | `parse(output_dir: Path, metadata: RunMetadata) -> list[ParsedResult]` | Walks the upstream output layout and emits `ParsedResult` objects |
  | `collect_files(...)` | Returns the `FileArtifact`s worth registering |
  | `SUPPORTED_PIPELINE_VERSIONS: list[str]` | Upstream versions this wrapper is validated against |

- `__init__.py` — re-exports those same three names from `parsers`.
- `apptainer_images.txt` — one OCI URI per line, read by
  `pipelines/pipelines/apptainer_manifest.py` (`#` comments,
  `@directive value` metadata). See the H-2 entry in
  `docs/jackpot_session_summary_and_backlog.md`.

`SUPPORTED_PIPELINE_VERSIONS` is a **module constant**. It has never
been a file, in any wrapper.

## What only three wrappers have

`cecret`, `viralrecon` and `walkercreek` — the Session J trio — also
carry `jackpot_wrapper.nf` plus a `register.py` that the wrapper's
REGISTER_RESULTS process invokes once the upstream pipeline has
finished writing output. The seven wrappers added in Sessions K-M have
neither, and nothing in the backend requires them.

**A new wrapper does not need a `.nf` file by default.** Whether the
Session J shim is the intended end state or an abandoned first approach
is an open question; answer it before copying the trio rather than
after.

## Tests

`pipelines/tests/`, not `tests/`. `test_pipeline_integration_e2e.py`
loads `(parse, collect_files, SUPPORTED_PIPELINE_VERSIONS)` from each
wrapper; `test_version_check.py` asserts every wrapper declares a
non-empty version list.

## Adding a wrapper: three registration points

Writing the `parsers/` package is not enough. A new wrapper is invisible
to the suite until it is registered in all three places, and each is in a
different file:

1. **`pipelines/tests/test_<name>_parsers.py`** — a per-wrapper test
   file. All ten existing wrappers have one; there is no shared parser
   test to extend instead. **Nothing enforces this** — skip it and the
   suite stays green with your parsers untested.

2. **A `PipelineCase` row in `_PIPELINE_CASES`** in
   `test_pipeline_integration_e2e.py`, **plus a fixture tree at
   `pipelines/tests/fixtures/<name>/`**. This one is self-enforcing from
   both directions: the test walks `pipelines/pipelines/` and fails on
   any wrapper missing from the matrix, then fails again on any matrix
   row whose fixture directory does not exist. Leave `expects_results` at
   its default unless the pipeline genuinely emits nothing — it is what
   catches a fixture that parses to zero `ParsedResult`s because a
   subdirectory got renamed.

3. **A `(module, upstream)` row in `_WRAPPED_PIPELINES`** in
   `test_version_check.py`, which parametrizes over it. **Nothing
   enforces this either** — there is no disk-completeness check, so a
   wrapper absent from the list simply never has its
   `SUPPORTED_PIPELINE_VERSIONS` checked, and the version gate the file
   exists to provide is bypassed without a word.

Note the asymmetry: **2 is the only one that fails if you forget it.**
Points 1 and 3 are registries keyed to something outside themselves, and
omission from either is silent — the exact failure mode Critical Rule 74
describes. Until they grow their own completeness checks, this list is
what stands in for them, so add all three in the same commit.

### What a fixture has to be

Lower than it looks. The 54 committed fixture files are **hand-written,
not captured runs** — synthetic values in genuinely real formats. The
mycosnp Snippy fixture is real `snippy 4.6.0` key/value shape with a
fabricated timestamp and invented variant counts; the typing TSV has the
real column names with made-up allele calls.

So what a new wrapper needs is the **directory nesting, the output
filenames, and the real header line of each table the parser reads**. It
does not need a pipeline execution. Getting those three wrong is the
expensive mistake, because parser and fixture then agree with each other
and with nothing else — the tests pass while proving nothing about real
output.

## Why this file is worded defensively

Until 2026-09-03 it claimed every wrapper directory contained
`jackpot_wrapper.nf`, `parsers/*.py` and a `SUPPORTED_PIPELINE_VERSIONS`
file, and listed the directories as `mycosnp-nf/` and `tb-profiler/`.
Seven wrappers have no `.nf`, the version list is a constant rather than
a file, and neither directory name was right — the text described the
Session J-M plan, not the result.

It went unnoticed because `scripts/check_docs.py` scans `docs/` plus
repo-root markdown, so a README beside source is outside the guard. The
cost was not hypothetical: `B-ZOO-MIRA-PHOENIX` was written from this
file, and the session prompt generated from that entry instructed a
`parsers.py` module, a `.nf` wrapper, a version *file*, and tests in a
directory that does not exist — while also saying "mirror `mycosnp/`
exactly". Critical Rule 70: verify the attachment before building on it.
