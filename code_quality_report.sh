#!/usr/bin/env bash
# code_quality_report.sh <directory> - run the quality toolchain on a dir and
# assemble a single Markdown report (Typora-friendly) plus raw per-tool logs.
# Missing tools are skipped and flagged, not fatal. Run check_tools.sh first.
#
# Grading: exit code alone is a poor signal. Several tools (radon cc, vulture)
# exit 0 whether or not they find anything, so an exit-0 "clean" can sit above a
# function with 55 branches. Others exit nonzero for reasons that are not
# findings at all. Where a tool has a countable finding format, this script
# grades on the count and reports it, and distinguishes "tool found things"
# from "tool failed to run".
set -uo pipefail

CAP=200   # max lines embedded per tool section; full output kept in raw/
export NO_COLOR=1   # ask tools not to colorize; belt-and-suspenders strip below
ESC="$(printf '\033')"   # for stripping any ANSI codes tools emit anyway

TARGET="${1:-}"
if [ -z "$TARGET" ]; then echo "usage: $0 <directory>" >&2; exit 1; fi
if [ ! -d "$TARGET" ]; then echo "not a directory: $TARGET" >&2; exit 1; fi
TARGET="$(cd "$TARGET" && pwd)"

base="$(basename "$TARGET")"
stamp="$(date +%Y%m%d_%H%M%S)"
OUTDIR="code_quality_${base}_${stamp}"
RAW="${OUTDIR}/raw"
mkdir -p "$RAW"
REPORT="${OUTDIR}/report.md"

SUMMARY="$(mktemp)"
DETAILS="$(mktemp)"
WARNINGS="$(mktemp)"
trap 'rm -f "$SUMMARY" "$DETAILS" "$WARNINGS"' EXIT

SECTION_NOTE=""     # one-off note printed under a section, then cleared
add_note() {        # append to SECTION_NOTE without clobbering what is already there
  if [ -n "$SECTION_NOTE" ]; then SECTION_NOTE="$SECTION_NOTE $1"; else SECTION_NOTE="$1"; fi
}
RUN_CWD=""          # if set, run the tool from this dir (some tools resolve deps vs CWD)
FORCE_SKIP=""       # if set, skip execution and record this reason
INFO_SECTION=""     # if set, an exit-0 run is labeled 'info' (not pass/fail)
COUNT_PATTERN=""    # if set, grade on count of matching lines, not exit code
COUNT_LABEL=""      # what the count means, e.g. "blocks graded C or worse"
INVALID_PATTERN=""  # if set and matched, the run is 'invalid' regardless of exit

# --- pre-flight: is the target the right scope to run tests from? -----------
# The classic failure: pyproject sets testpaths relative to the repo root, the
# script is pointed at a subdirectory, pytest collects nothing, and coverage
# reports a tiny denominator that looks like a catastrophic score. Warn loudly.
GIT_TOPLEVEL=""
if git -C "$TARGET" rev-parse --show-toplevel >/dev/null 2>&1; then
  GIT_TOPLEVEL="$(git -C "$TARGET" rev-parse --show-toplevel)"
fi
if [ -n "$GIT_TOPLEVEL" ] && [ "$GIT_TOPLEVEL" != "$TARGET" ]; then
  {
    printf '> **Scope warning.** The target is a subdirectory of the repository at '
    printf '`%s`. If `pyproject.toml` declares `testpaths` relative to the repo ' "$GIT_TOPLEVEL"
    printf 'root, pytest will collect nothing here and the coverage figure below will be '
    printf 'measured against a near-empty denominator. Re-run against the repo root for a '
    printf 'meaningful test and coverage result.\n\n'
  } >>"$WARNINGS"
  printf '  %-34s %s\n' "SCOPE" "target is not the repo root" >&2
fi

run_tool() {
  # $1 title  $2 cmd-to-check  then the full command to execute
  local title="$1" cmd="$2"; shift 2
  local slug raw raw_rel status exit_code dur total findings
  slug="$(printf '%s' "$title" | tr -cs 'A-Za-z0-9' '_' | sed 's/^_//; s/_$//')"
  raw="${RAW}/${slug}.txt"
  raw_rel="raw/${slug}.txt"   # relative to report.md, so links resolve in an editor
  findings="-"

  if [ -n "$FORCE_SKIP" ]; then
    status="skipped"; exit_code="-"; dur="-"
    echo "$FORCE_SKIP" >"$raw"
  elif ! command -v "$cmd" >/dev/null 2>&1; then
    status="skipped"; exit_code="-"; dur="-"
    echo "tool '$cmd' not installed - run check_tools.sh" >"$raw"
  else
    local start; start="$(date +%s)"
    if [ -n "$RUN_CWD" ]; then
      ( cd "$RUN_CWD" && "$@" ) >"$raw" 2>&1
    else
      "$@" >"$raw" 2>&1
    fi
    exit_code=$?
    dur="$(( $(date +%s) - start ))s"

    # strip ANSI before any pattern matching, so counts are not thrown off
    if [ -s "$raw" ]; then
      sed "s/${ESC}\[[0-9;]*[a-zA-Z]//g" "$raw" >"${raw}.clean" && mv "${raw}.clean" "$raw"
    fi

    # count findings where the tool has a countable format
    if [ -n "$COUNT_PATTERN" ]; then
      if [ -s "$raw" ]; then
        findings="$(grep -cE -e "$COUNT_PATTERN" "$raw" 2>/dev/null || true)"
      else
        findings=0
      fi
      findings="${findings:-0}"
    fi

    # --- status ---
    # A run is invalid when the tool ran but its output shows it measured
    # nothing meaningful. That is neither a pass nor a finding; it means the
    # result must not be believed.
    if [ -n "$INVALID_PATTERN" ] && [ -s "$raw" ] && grep -qE -e "$INVALID_PATTERN" "$raw"; then
      status="INVALID"
    elif [ "$findings" != "-" ]; then
      if [ "$findings" -gt 0 ]; then
        status="review"
      elif [ "$exit_code" -ne 0 ]; then
        # nonzero exit but nothing matched the finding pattern: the tool itself
        # failed, or its output format changed. Either way, read it.
        status="error"
      else
        status="clean"
      fi
    elif [ "$exit_code" -eq 0 ]; then
      status="clean"
    else
      status="review"
    fi
    if [ -n "$INFO_SECTION" ] && [ "$status" = "clean" ]; then status="info"; fi
  fi

  printf '| %s | %s | %s | %s | %s |\n' \
    "$title" "$status" "$findings" "$exit_code" "$dur" >>"$SUMMARY"

  {
    printf '### %s\n\n' "$title"
    printf '`status: %s`  `findings: %s`  `exit: %s`  `time: %s`  `raw: %s`\n\n' \
      "$status" "$findings" "$exit_code" "$dur" "$raw_rel"
    [ -n "$COUNT_LABEL" ] && [ "$findings" != "-" ] && \
      printf '> Findings counted as: %s.\n\n' "$COUNT_LABEL"
    [ "$status" = "INVALID" ] && \
      printf '> **This result is not trustworthy.** The tool ran but measured nothing meaningful; read the output before drawing any conclusion from it.\n\n'
    [ "$status" = "error" ] && \
      printf '> **Nonzero exit with no parsed findings.** The tool likely failed to run rather than finding problems. Read the raw output.\n\n'
    [ -n "$SECTION_NOTE" ] && printf '> %s\n\n' "$SECTION_NOTE"
    printf '```text\n'
    if [ -s "$raw" ]; then
      head -n "$CAP" "$raw"
      total="$(wc -l <"$raw" | tr -d ' ')"
      if [ "$total" -gt "$CAP" ]; then
        printf '\n... [truncated: showing %s of %s lines, full output in %s] ...\n' \
          "$CAP" "$total" "$raw"
      fi
    else
      printf '(no output)\n'
    fi
    printf '```\n\n'
  } >>"$DETAILS"

  SECTION_NOTE=""; RUN_CWD=""; FORCE_SKIP=""; INFO_SECTION=""
  COUNT_PATTERN=""; COUNT_LABEL=""; INVALID_PATTERN=""
  printf '  %-34s %-8s %s\n' "$title" "$status" "$findings" >&2
}

# --- test + coverage ------------------------------------------------------
# Executing a suite is the slowest and least reliable thing this script can do:
# it needs the project's dependencies, and on a container-backed suite it needs
# a running Docker daemon. When Docker is absent, testcontainers does not fail
# fast, it retries, and a 60-second suite becomes an unbounded spin at 100% CPU.
# So: prefer reading a coverage artifact that already exists, run the suite only
# when asked, and never run it blind into a missing daemon.

COVERAGE_SOURCE=""   # set by find_coverage_artifact

find_coverage_artifact() {
  local c
  for c in "$TARGET/coverage.xml" "$TARGET/.coverage" \
           "$TARGET/htmlcov/index.html" "$TARGET/coverage.json"; do
    [ -f "$c" ] && { COVERAGE_SOURCE="$c"; return 0; }
  done
  return 1
}

report_existing_coverage() {
  local src="$COVERAGE_SOURCE" age
  age="$(python3 - "$src" <<'PY' 2>/dev/null || echo "unknown"
import os, sys, time
m = os.path.getmtime(sys.argv[1])
h = (time.time() - m) / 3600
print(f"{h:.1f} hours old" if h < 48 else f"{h/24:.1f} days old")
PY
)"
  echo "# source: $src ($age)"
  echo "# The suite was NOT executed. This is a recorded result, not a fresh one."
  echo
  case "$src" in
    *coverage.xml)
      python3 - "$src" <<'PY'
import sys, xml.etree.ElementTree as ET
r = ET.parse(sys.argv[1]).getroot()
lr = float(r.get("line-rate", 0)) * 100
print(f"TOTAL line coverage: {lr:.2f}%")
va, vc = r.get("lines-valid"), r.get("lines-covered")
if va and vc:
    print(f"lines covered: {vc} of {va}")
# A file that measured thousands of lines and covered none of them is not a
# 0% score, it is a broken artifact: the run collected nothing, or coverage
# was pointed at source paths the tests never imported. Reporting it as a
# real number is worse than reporting nothing.
if lr == 0 and int(va or 0) > 0:
    print()
    print(f"!! INVALID: this artifact claims 0.00% over {va} measured lines.")
    print("!! That is a failed coverage run, not a real score — the data file")
    print("!! never got mapped to the source. Delete it and re-run with")
    print("!! RUN_TESTS=1, or regenerate it from the project's own test command.")
print()
print("Per-package:")
for pkg in r.iter("package"):
    print(f"  {float(pkg.get('line-rate',0))*100:6.2f}%  {pkg.get('name')}")
PY
      ;;
    *.coverage)
      ( cd "$TARGET" && coverage report 2>&1 ) || \
        echo "could not read .coverage (needs the 'coverage' package on PATH)"
      ;;
    *)
      echo "Found $src but this script only parses coverage.xml and .coverage."
      echo "Generate one with: coverage xml"
      ;;
  esac
}

# Does this project's suite need a container runtime?
needs_docker() {
  grep -rqE 'testcontainers' "$TARGET/pyproject.toml" "$TARGET/requirements.txt" \
      2>/dev/null && return 0
  [ -f "$TARGET/docker-compose.yml" ] || [ -f "$TARGET/compose.yml" ] && return 0
  return 1
}

docker_up() {
  command -v docker >/dev/null 2>&1 || return 1
  docker info >/dev/null 2>&1
}

docker_hint() {
  echo "Docker is not reachable." >&2
  if command -v colima >/dev/null 2>&1; then
    echo "  This project appears to use Colima. Start it with:  colima start" >&2
  fi
  echo "  Then confirm with:  docker info" >&2
  if [ -n "${DOCKER_HOST:-}" ]; then
    echo "  DOCKER_HOST is set to: ${DOCKER_HOST}" >&2
  else
    echo "  DOCKER_HOST is not set. A Colima socket usually needs:" >&2
    echo "    export DOCKER_HOST=\"unix://\$HOME/.colima/default/docker.sock\"" >&2
  fi
}

run_tests() {
  case "$TEST_MODE" in
    uv)
      echo "# runner: uv run (project env + ephemeral pytest & coverage)"
      ${TIMEOUT_CMD:+$TIMEOUT_CMD "$TEST_TIMEOUT"} \
        uv run --with pytest --with coverage -- \
        sh -c 'coverage run -m pytest -q -p no:cacheprovider; rc=$?; echo; echo "# coverage"; coverage report; exit $rc'
      ;;
    env)
      echo "# runner: active environment (coverage run -m pytest)"
      ${TIMEOUT_CMD:+$TIMEOUT_CMD "$TEST_TIMEOUT"} \
        sh -c 'coverage run -m pytest -q -p no:cacheprovider; rc=$?; echo; echo "# coverage"; coverage report; exit $rc'
      ;;
    artifact)
      report_existing_coverage
      ;;
  esac
}

# --- git history: informational signals for where risk and knowledge sit ---
churn_hotspots() {
  git -C "$TARGET" log --format=format: --name-only --since='12 months ago' -- . \
    | grep -E '\.(py|sh)$' | sort | uniq -c | sort -rn | head -20
  return 0
}
bus_factor() {
  # One `git log` per file is O(files x history) and took minutes on a large
  # repo. Walk history once instead and let awk find single-author files.
  git -C "$TARGET" log --format='C%an' --name-only --since='36 months ago' -- . \
    | awk '
        /^C/ { author = substr($0, 2); next }
        /\.(py|sh)$/ { if (!seen[$0 SUBSEP author]++) count[$0]++ }
        END { for (f in count) if (count[f] == 1) print "1 author\t" f }
      ' | sort | head -20
  return 0
}
bugfix_clusters() {
  git -C "$TARGET" log --since='24 months ago' -i --grep='fix\|bug\|hotfix' \
    --format=format: --name-only -- . \
    | grep -E '\.(py|sh)$' | sort | uniq -c | sort -rn | head -20
  return 0
}

echo "Scanning $TARGET" >&2
printf '  %-34s %-8s %s\n' "CHECK" "STATUS" "FINDINGS" >&2

# --- test + coverage (run first: the strongest maintainability signal) ---
# Precedence, and the reasoning behind it:
#   1. RUN_TESTS=1        you explicitly asked for a fresh run
#   2. SKIP_TESTS=1       you explicitly asked to skip
#   3. a coverage artifact exists -> read it, do not execute
#   4. otherwise execute, but only after Docker is confirmed if the suite needs it
TEST_TIMEOUT="${TEST_TIMEOUT:-900}"   # hard ceiling so a hung suite cannot run forever
TIMEOUT_CMD=""
if command -v timeout >/dev/null 2>&1; then TIMEOUT_CMD="timeout"
elif command -v gtimeout >/dev/null 2>&1; then TIMEOUT_CMD="gtimeout"; fi

pick_test_mode() {
  if [ "${SKIP_TESTS:-0}" = "1" ]; then
    TEST_MODE=none
    SKIP_REASON="Skipped: SKIP_TESTS=1."
    return
  fi

  if [ "${RUN_TESTS:-0}" != "1" ] && find_coverage_artifact; then
    TEST_MODE=artifact
    return
  fi

  # A fresh run was requested, or there is nothing to read. Check the runtime
  # the suite needs BEFORE launching it, because the failure mode otherwise is
  # a silent multi-hour spin rather than an error.
  if needs_docker && ! docker_up; then
    echo >&2
    echo "  This project's tests need Docker (testcontainers), and it is not running." >&2
    docker_hint
    echo >&2
    if [ -t 0 ]; then
      while true; do
        printf '  Start Docker now, then choose: [r]etry  [s]kip tests  [a]bort: ' >&2
        read -r ans
        case "$ans" in
          r|R) if docker_up; then echo "  Docker is up. Continuing." >&2; break
               else echo "  Still not reachable." >&2; fi ;;
          s|S) TEST_MODE=none
               SKIP_REASON="Skipped: Docker was not reachable and the suite needs it (testcontainers)."
               return ;;
          a|A) echo "  Aborting. Nothing was written." >&2; exit 1 ;;
          *)   echo "  Answer r, s, or a." >&2 ;;
        esac
      done
    else
      TEST_MODE=none
      SKIP_REASON="Skipped: Docker was not reachable and the suite needs it (testcontainers). Non-interactive run, so the script did not prompt."
      return
    fi
  fi

  if command -v uv >/dev/null 2>&1 && { [ -f "$TARGET/pyproject.toml" ] || [ -f "$TARGET/uv.lock" ]; }; then
    TEST_MODE=uv
  elif python3 -c 'import pytest, coverage' >/dev/null 2>&1; then
    TEST_MODE=env
  else
    TEST_MODE=none
    SKIP_REASON="No way to run tests. Either make this a uv project (pyproject.toml/uv.lock) so 'uv run' can supply the env, or activate the project's venv with pytest and coverage installed."
  fi
}

SKIP_REASON=""
pick_test_mode

RUN_CWD="$TARGET"
# keep every test artifact out of the inherited repo
TESTTMP="$(mktemp -d)"
had_uvlock=0; [ -f "$TARGET/uv.lock" ] && had_uvlock=1
export UV_PROJECT_ENVIRONMENT="${TESTTMP}/venv"   # no .venv in the repo
export COVERAGE_FILE="${TESTTMP}/.coverage"        # no .coverage in the repo
export PYTHONDONTWRITEBYTECODE=1                    # no __pycache__ in the repo
case "$TEST_MODE" in
  none)
    FORCE_SKIP="$SKIP_REASON"
    run_tool "Tests + coverage"               run_tests run_tests
    ;;
  artifact)
    SECTION_NOTE="Read from an existing coverage artifact; the suite was not executed. This is fast and cannot hang, but it is only as current as the file. Re-run with RUN_TESTS=1 to execute the suite instead."
    INVALID_PATTERN='could not read|only parses|!! INVALID|No data to report'
    run_tool "Tests + coverage (recorded)"    run_tests run_tests
    ;;
  *)
    INVALID_PATTERN='no tests ran|No data was collected|no-data-collected|collected 0 items'
    SECTION_NOTE="Coverage TOTAL row is at the bottom of the output. If the status is INVALID, the suite did not run: check that you are pointed at the directory pytest is configured for. Bounded by TEST_TIMEOUT=${TEST_TIMEOUT}s."
    run_tool "Tests + coverage (pytest)"      run_tests run_tests
    ;;
esac
# leave no trace: remove a uv.lock only if we created it
[ "$had_uvlock" -eq 0 ] && rm -f "$TARGET/uv.lock" 2>/dev/null
rm -rf "$TESTTMP"
unset UV_PROJECT_ENVIRONMENT COVERAGE_FILE PYTHONDONTWRITEBYTECODE

# --- static checks ---
# static analyzers: exclude common noise dirs so a committed/local venv can't skew results
EXC="*/.venv/*,*/venv/*,*/build/*,*/dist/*,*/node_modules/*,*/.tox/*,*/.git/*"

# --- prefer the project's own pinned toolchain ------------------------------
# Lint and security rule sets change between releases. An ambient ruff can
# report a hundred violations that the project's pinned ruff does not have,
# which reads as rot when it is version drift: the project's CI and
# pre-commit are green, this report is not, and neither is wrong. So when the
# target is a uv project and the tool is installed in its environment, run
# that copy and say which one ran.
UV_PREFIX=()
if command -v uv >/dev/null 2>&1 && [ -f "$TARGET/pyproject.toml" ]; then
  UV_PREFIX=(uv run --no-sync --project "$TARGET" --)
fi

TOOL_CMD=()      # argv prefix for the chosen copy of the tool
TOOL_BIN=""      # what run_tool checks for on PATH
pick_tool() {
  local tool="$1" ver
  if [ ${#UV_PREFIX[@]} -gt 0 ] && ver="$("${UV_PREFIX[@]}" "$tool" --version 2>/dev/null | head -1)"; then
    TOOL_CMD=("${UV_PREFIX[@]}" "$tool"); TOOL_BIN="uv"
    add_note "Ran the project's pinned copy (\`${ver}\`) from its uv environment, not the ambient one."
  else
    TOOL_CMD=("$tool"); TOOL_BIN="$tool"
    if [ ${#UV_PREFIX[@]} -gt 0 ]; then
      add_note "**Ambient \`${tool}\`, not the project's.** It is not installed in the target's uv environment, so this ran whatever is on PATH. Rule sets differ between releases; findings here may not reproduce in the project's own CI."
    fi
  fi
}

pick_tool ruff
COUNT_PATTERN='^[[:space:]]*[0-9]+[[:space:]]+[A-Z]+[0-9]+'
COUNT_LABEL="distinct rule violations from \`--statistics\`"
run_tool "Ruff (lint)"          "$TOOL_BIN" "${TOOL_CMD[@]}" check --statistics "$TARGET"

pick_tool pyrefly
COUNT_PATTERN='^ERROR '
COUNT_LABEL="type errors"
run_tool "Pyrefly (types)"      "$TOOL_BIN" "${TOOL_CMD[@]}" check "$TARGET"

# radon cc exits 0 whether or not it finds anything, so exit code is useless here.
COUNT_PATTERN='- [C-F] \([0-9]+\)'
COUNT_LABEL="code blocks graded C or worse (D and F are the ones to act on)"
SECTION_NOTE="Lists only blocks graded C or worse. Grade F means the function has more independent paths than anyone can hold in their head or test exhaustively. Cross-reference the churn and bug-fix sections: complex plus frequently-changed plus frequently-fixed is your highest-risk code."
run_tool "Radon (cyclomatic complexity)"      radon     radon cc -s -n C -i "$EXC" "$TARGET"

# radon mi also always exits 0; count anything below grade A.
COUNT_PATTERN='- [B-F] \('
COUNT_LABEL="files with a maintainability index below grade A"
run_tool "Radon (maintainability index)"      radon     radon mi -s -i "$EXC" "$TARGET"

# vulture's default 60% confidence is mostly noise on codebases with dynamic
# dispatch, string-keyed registries, or enum constants referenced by value.
COUNT_PATTERN='unused (variable|function|method|class|import|property|attribute)'
COUNT_LABEL="possible dead-code findings"
SECTION_NOTE="Raised to 80% minimum confidence. At the 60% default, constant registries and dynamically-referenced names dominate the output and drown the real findings. Lower it with --min-confidence if you want the long tail."
run_tool "Vulture (dead code)"                vulture   vulture "$TARGET" --exclude "$EXC" --min-confidence 80

# Tests are excluded: pytest's bare `assert` trips B101 once per assertion, and
# on any real suite that single rule outnumbers every genuine finding by an
# order of magnitude. Counting is on Medium/High severity for the same reason —
# a total that is 90% Low pattern-matches is not a number anyone can grade on.
# The full output below still contains every Low finding.
BANDIT_EXC="${EXC},*/tests/*,*/test/*,*/test_*.py,*_test.py,*/conftest.py"
pick_tool bandit
COUNT_PATTERN='^   Severity: (Medium|High)'
COUNT_LABEL="Medium- and High-severity findings (Low is counted in the raw output but excluded here; it is dominated by pattern matches)"
add_note "Test files are excluded — \`assert\` trips B101 on every line and buries the real findings. Drop the test globs from \`BANDIT_EXC\` to include them."
run_tool "Bandit (security)"    "$TOOL_BIN" "${TOOL_CMD[@]}" -r "$TARGET" -x "$BANDIT_EXC"

# Auditing the ambient environment answers a question nobody asked: it reports
# on whatever happens to be installed on this machine, not on what the project
# pins. Prefer requirements.txt, then the uv lockfile exported to the same
# format. Only fall back to the environment when there is nothing to read.
run_pip_audit() {
  local req
  if [ -f "$TARGET/requirements.txt" ]; then
    pip-audit -r "$TARGET/requirements.txt"
  elif [ -f "$TARGET/uv.lock" ]; then
    req="$(mktemp)"
    if uv export --project "$TARGET" --format requirements-txt \
         --all-packages --no-emit-workspace --no-dev -q >"$req" 2>/dev/null; then
      pip-audit -r "$req"; local rc=$?; rm -f "$req"; return $rc
    fi
    rm -f "$req"
    echo "uv export failed; falling back to the ambient environment." >&2
    pip-audit
  else
    pip-audit
  fi
}

if [ -f "$TARGET/requirements.txt" ]; then
  SECTION_NOTE="Audited requirements.txt."
elif [ -f "$TARGET/uv.lock" ] && command -v uv >/dev/null 2>&1; then
  SECTION_NOTE="Audited the project's \`uv.lock\` (exported to requirements format, runtime deps only). This is what the project actually pins, not what happens to be installed on this machine."
else
  SECTION_NOTE="No requirements.txt or uv.lock found. This audited the active Python environment, not the project's pinned deps — treat a clean result as unproven."
fi
COUNT_PATTERN='(PYSEC|GHSA|CVE)-[0-9]'
COUNT_LABEL="advisory rows (one package can appear several times; read the Name column for the number of affected packages)"
run_tool "pip-audit (dependency CVEs)"      pip-audit run_pip_audit

# deptry resolves its dependency spec from CWD and needs a real [project],
# [tool.poetry], or [tool.pdm] table. A uv *virtual workspace* root has none —
# it only lists members — so pointing deptry at the root aborts the whole check
# with DependencySpecificationNotFoundError. Fall back to running it once per
# member that does declare dependencies.
has_dep_spec() { grep -qE '^\[(project\]|tool\.poetry|tool\.pdm)' "$1/pyproject.toml" 2>/dev/null; }

# deptry maps a distribution name to its import name by introspecting the
# installed package. With nothing installed it guesses from the name, and
# every package whose import name differs from its distribution name
# (python-jose -> jose, PyYAML -> yaml, google-cloud-* -> google) becomes a
# false DEP001 "imported but missing". Running it inside the project's
# environment removes that entire class of noise, so prefer that.
deptry_in() {
  local dir="$1"
  if command -v uv >/dev/null 2>&1 && [ -f "$dir/pyproject.toml" ]; then
    ( cd "$dir" && uv run --project . --with deptry -- deptry . )
  else
    ( cd "$dir" && deptry . )
  fi
}

run_deptry() {
  local d rc=0 found=0
  if has_dep_spec "$TARGET" || [ -f "$TARGET/requirements.txt" ] || [ -f "$TARGET/setup.py" ]; then
    deptry_in "$TARGET"; return $?
  fi
  echo "# The target declares no dependencies of its own (uv virtual workspace root)."
  echo "# Running deptry once per member that does."
  echo
  for d in "$TARGET"/*/; do
    has_dep_spec "${d%/}" || continue
    found=1
    printf '=== %s ===\n' "$(basename "${d%/}")"
    deptry_in "${d%/}" || rc=1
    echo
  done
  if [ "$found" -eq 0 ]; then
    echo "No pyproject.toml with a [project], [tool.poetry], or [tool.pdm] section at the target or one level below."
    return 1
  fi
  return $rc
}

if [ -f "$TARGET/pyproject.toml" ] || [ -f "$TARGET/requirements.txt" ] || \
   [ -f "$TARGET/setup.py" ] || [ -f "$TARGET/setup.cfg" ]; then
  COUNT_PATTERN='DEP[0-9]{3}'
  COUNT_LABEL="dependency issues (DEP001 undeclared imports are the real ones; DEP002 'defined but not used' is expected noise in a monorepo/workspace, where a dependency is used by a sibling package)"
  run_tool "deptry (dependency hygiene)"      deptry    run_deptry
else
  FORCE_SKIP="No pyproject.toml, requirements.txt, or setup.py in the target. deptry needs a declared dependency spec to run."
  run_tool "deptry (dependency hygiene)"      deptry    run_deptry
fi

# --- git history (informational: where change and knowledge concentrate) ---
if git -C "$TARGET" rev-parse >/dev/null 2>&1; then
  INFO_SECTION=1
  SECTION_NOTE="Most-changed files in the last 12 months. Cross-reference with the complexity output: high churn plus high complexity is your highest-risk code."
  run_tool "Churn hotspots (git)"             git       churn_hotspots

  INFO_SECTION=1
  SECTION_NOTE="Files touched by only one author. These are knowledge silos and onboarding risk. On a single-developer project this measures nothing; read it when a second contributor arrives."
  run_tool "Bus factor (git)"                 git       bus_factor

  INFO_SECTION=1
  SECTION_NOTE="Files appearing most in fix/bug commits over 24 months. Repeated fixes signal structural weakness rather than bad luck."
  run_tool "Bug-fix clusters (git)"           git       bugfix_clusters
else
  FORCE_SKIP="Target is not a git repository, so history-based signals are unavailable."
  run_tool "Git history"                      git       true
fi

# --- context for the header ---
py_count="$(find "$TARGET" -type f -name '*.py' \
  -not -path '*/.git/*' -not -path '*/.venv/*' -not -path '*/venv/*' \
  -not -path '*/node_modules/*' -not -path '*/build/*' -not -path '*/dist/*' 2>/dev/null | wc -l | tr -d ' ')"
sh_count="$(find "$TARGET" -type f -name '*.sh' \
  -not -path '*/.git/*' -not -path '*/.venv/*' -not -path '*/venv/*' \
  -not -path '*/node_modules/*' -not -path '*/build/*' -not -path '*/dist/*' 2>/dev/null | wc -l | tr -d ' ')"

git_line="not a git repository"
if git -C "$TARGET" rev-parse >/dev/null 2>&1; then
  gb="$(git -C "$TARGET" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  gc="$(git -C "$TARGET" log -1 --format='%h %s' 2>/dev/null)"
  git_line="branch \`${gb}\`, last commit \`${gc}\`"
fi

# --- assemble report ---
{
  printf '# Code Quality Report\n\n'
  printf -- '- Target: `%s`\n' "$TARGET"
  printf -- '- Generated: %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')"
  printf -- '- Files: %s Python, %s shell\n' "$py_count" "$sh_count"
  printf -- '- Git: %s\n\n' "$git_line"

  [ -s "$WARNINGS" ] && cat "$WARNINGS"

  printf '## Summary\n\n'
  printf '| Check | Status | Findings | Exit | Time |\n'
  printf '|---|---|---|---|---|\n'
  cat "$SUMMARY"
  printf '\n'
  printf 'Status legend: `clean` ran and found nothing. `review` ran and found something worth reading. '
  printf '`error` exited nonzero but produced no parsable findings, which usually means the tool failed rather than the code. '
  printf '`INVALID` ran but measured nothing meaningful, so the result must not be believed. '
  printf '`info` informational output (git history), not pass/fail. `skipped` tool unavailable or not applicable.\n\n'
  printf 'The Findings column is the count of actual findings where the tool has a countable output format. '
  printf 'It exists because exit code alone is misleading: radon exits 0 whether or not it finds a function with fifty branches, '
  printf 'and a nonzero exit often means a tool could not run rather than that it found a problem. '
  printf 'Grade on the Findings column; use Exit only to spot tools that broke.\n\n'

  printf '## Details\n\n'
  cat "$DETAILS"
} >"$REPORT"

echo >&2
echo "Report: $REPORT" >&2
echo "Raw logs: $RAW/" >&2
printf '%s\n' "$REPORT"
