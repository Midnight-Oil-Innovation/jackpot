#!/usr/bin/env bash
# code_quality_report.sh <directory> - run the quality toolchain on a dir and
# assemble a single Markdown report (Typora-friendly) plus raw per-tool logs.
# Missing tools are skipped and flagged, not fatal. Run check_tools.sh first.
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
trap 'rm -f "$SUMMARY" "$DETAILS"' EXIT

SECTION_NOTE=""          # one-off note printed under a section, then cleared
RUN_CWD=""               # if set, run the tool from this dir (some tools resolve deps vs CWD)
FORCE_SKIP=""            # if set, skip execution and record this reason
INFO_SECTION=""          # if set, an exit-0 run is labeled 'info' (informational, not pass/fail)
NONEMPTY_IS_REVIEW=""    # if set, grade on "did the tool print anything" not exit code —
                         # radon cc/mi and vulture exit 0 whether or not they find anything

run_tool() {
  # $1 title  $2 cmd-to-check  then the full command to execute
  local title="$1" cmd="$2"; shift 2
  local slug raw raw_rel status exit_code dur total
  slug="$(printf '%s' "$title" | tr -cs 'A-Za-z0-9' '_' | sed 's/^_//; s/_$//')"
  raw="${RAW}/${slug}.txt"
  raw_rel="raw/${slug}.txt"   # relative to report.md, so links resolve in an editor

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
    if [ -n "$NONEMPTY_IS_REVIEW" ]; then
      if [ -s "$raw" ]; then status="review"; else status="clean"; fi
    elif [ "$exit_code" -eq 0 ]; then status="clean"; else status="review"; fi
    if [ -n "$INFO_SECTION" ] && [ "$status" = "clean" ]; then status="info"; fi
  fi

  # strip any ANSI escape sequences so the report stays clean in editors
  if [ -s "$raw" ]; then
    sed "s/${ESC}\[[0-9;]*[a-zA-Z]//g" "$raw" >"${raw}.clean" && mv "${raw}.clean" "$raw"
  fi

  printf '| %s | %s | %s | %s |\n' "$title" "$status" "$exit_code" "$dur" >>"$SUMMARY"

  {
    printf '### %s\n\n' "$title"
    printf '`status: %s`  `exit: %s`  `time: %s`  `raw: %s`\n\n' \
      "$status" "$exit_code" "$dur" "$raw_rel"
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

  SECTION_NOTE=""; RUN_CWD=""; FORCE_SKIP=""; INFO_SECTION=""; NONEMPTY_IS_REVIEW=""
  printf '  %-34s %s\n' "$title" "$status" >&2
}

# --- test + coverage: needs the project's own deps importable, so prefer
# 'uv run' (project env + ephemeral pytest/coverage); else the active env ---
# When the suite needs Docker (testcontainers) and Docker isn't reachable,
# testcontainers doesn't fail fast — it retries, turning a 60s suite into an
# unbounded spin. Check reachability before launching, and bound the run with
# a timeout regardless, so a hung suite can't run forever.
TEST_TIMEOUT="${TEST_TIMEOUT:-900}"
TIMEOUT_CMD=""
if command -v timeout >/dev/null 2>&1; then TIMEOUT_CMD="timeout"
elif command -v gtimeout >/dev/null 2>&1; then TIMEOUT_CMD="gtimeout"; fi

needs_docker() {
  grep -rqE 'testcontainers' "$TARGET/pyproject.toml" "$TARGET/requirements.txt" \
      2>/dev/null && return 0
  { [ -f "$TARGET/docker-compose.yml" ] || [ -f "$TARGET/compose.yml" ]; } && return 0
  return 1
}
docker_up() {
  command -v docker >/dev/null 2>&1 || return 1
  docker info >/dev/null 2>&1
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
  esac
}

# --- git history: informational signals for where risk and knowledge sit ---
churn_hotspots() {
  git -C "$TARGET" log --format=format: --name-only --since='12 months ago' -- . \
    | grep -E '\.(py|sh)$' | grep -vE "$GEN_RE" | sort | uniq -c | sort -rn | head -20
  return 0
}
bus_factor() {
  # One `git log` per file is O(files x history) and takes minutes on a large
  # repo. Walk history once instead and let awk find single-author files.
  git -C "$TARGET" log --format='C%an' --name-only --since='36 months ago' -- . \
    | awk '
        /^C/ { author = substr($0, 2); next }
        /\.(py|sh)$/ { if (!seen[$0 SUBSEP author]++) count[$0]++ }
        END { for (f in count) if (count[f] == 1) print "1 author\t" f }
      ' | grep -vE "$GEN_RE" | sort | head -20
  return 0
}
bugfix_clusters() {
  git -C "$TARGET" log --since='24 months ago' -i --grep='fix\|bug\|hotfix' \
    --format=format: --name-only -- . \
    | grep -E '\.(py|sh)$' | grep -vE "$GEN_RE" | sort | uniq -c | sort -rn | head -20
  return 0
}

echo "Scanning $TARGET" >&2

# --- test + coverage (run first: the strongest maintainability signal) ---
TEST_SKIP_REASON=""
if needs_docker && ! docker_up; then
  TEST_MODE=none
  TEST_SKIP_REASON="Skipped: this project's tests need Docker (testcontainers), and it is not reachable. Start it (e.g. \`colima start\`, or check \`docker info\`) and re-run."
elif command -v uv >/dev/null 2>&1 && { [ -f "$TARGET/pyproject.toml" ] || [ -f "$TARGET/uv.lock" ]; }; then
  TEST_MODE=uv
elif python3 -c 'import pytest, coverage' >/dev/null 2>&1; then
  TEST_MODE=env
else
  TEST_MODE=none
  TEST_SKIP_REASON="No way to run tests. Either make this a uv project (pyproject.toml/uv.lock) so 'uv run' can supply the env, or activate the project's venv with pytest and coverage installed."
fi

RUN_CWD="$TARGET"
# keep every test artifact out of the inherited repo
TESTTMP="$(mktemp -d)"
had_uvlock=0; [ -f "$TARGET/uv.lock" ] && had_uvlock=1
export UV_PROJECT_ENVIRONMENT="${TESTTMP}/venv"   # no .venv in the repo
export COVERAGE_FILE="${TESTTMP}/.coverage"        # no .coverage in the repo
export PYTHONDONTWRITEBYTECODE=1                    # no __pycache__ in the repo
if [ "$TEST_MODE" = "none" ]; then
  FORCE_SKIP="$TEST_SKIP_REASON"
  run_tool "Tests + coverage (pytest)"        run_tests run_tests
else
  SECTION_NOTE="Coverage TOTAL row is at the bottom of the output. Low or zero coverage is the biggest risk multiplier on an inherited repo. Bounded by TEST_TIMEOUT=${TEST_TIMEOUT}s."
  run_tool "Tests + coverage (pytest)"        run_tests run_tests
fi
# leave no trace: remove a uv.lock only if we created it
[ "$had_uvlock" -eq 0 ] && rm -f "$TARGET/uv.lock" 2>/dev/null
rm -rf "$TESTTMP"
unset UV_PROJECT_ENVIRONMENT COVERAGE_FILE PYTHONDONTWRITEBYTECODE

# --- static checks (the commands from the table) ---
# Exclusions: noise dirs (committed/local venv, build output) plus auto-generated
# code you would never hand-edit (alembic migrations, *_generated.py, protobuf).
# EXC is a glob set for vulture/bandit/ruff and radon's -e; DEPTRY_EXC is a regex.
EXC="*/.venv/*,*/venv/*,*/build/*,*/dist/*,*/node_modules/*,*/.tox/*,*/.git/*,*/migrations/*,*_generated.py,*_pb2.py,*_pb2_grpc.py"
DEPTRY_EXC='(^|/)(\.venv|venv|build|dist|node_modules|migrations)/|_generated\.py$|_pb2(_grpc)?\.py$'
GEN_RE='(/migrations/|_generated\.py$|_pb2(_grpc)?\.py$)'   # git-log path filter

# Lint/security rule sets change between releases. An ambient ruff/pyrefly/
# bandit can report findings the project's own pinned copy doesn't have (or
# miss ones it does) — version drift, not rot. When the target is a uv
# project and the tool is installed in its environment, run that copy and say
# which one ran, so this report agrees with what CI and pre-commit enforce.
UV_PREFIX=()
if command -v uv >/dev/null 2>&1 && [ -f "$TARGET/pyproject.toml" ]; then
  UV_PREFIX=(uv run --no-sync --project "$TARGET" --)
fi
TOOL_CMD=(); TOOL_BIN=""
pick_tool() {
  local tool="$1" ver
  if [ ${#UV_PREFIX[@]} -gt 0 ] && ver="$("${UV_PREFIX[@]}" "$tool" --version 2>/dev/null | head -1)"; then
    TOOL_CMD=("${UV_PREFIX[@]}" "$tool"); TOOL_BIN="uv"
    SECTION_NOTE="Ran the project's pinned copy (\`${ver}\`) from its uv environment, not the ambient one."
  else
    TOOL_CMD=("$tool"); TOOL_BIN="$tool"
    if [ ${#UV_PREFIX[@]} -gt 0 ]; then
      SECTION_NOTE="Ambient \`${tool}\`, not the project's — it isn't installed in the target's uv environment, so this ran whatever's on PATH. Findings here may not match the project's own CI."
    fi
  fi
}

pick_tool ruff
run_tool "Ruff (lint)"          "$TOOL_BIN" "${TOOL_CMD[@]}" check --statistics --exclude "$EXC" "$TARGET"

pick_tool pyrefly
run_tool "Pyrefly (types)"      "$TOOL_BIN" "${TOOL_CMD[@]}" check "$TARGET"

# radon cc/mi exit 0 whether or not they find anything, so grade on output
# instead: empty (nothing at or worse than the threshold) is the only "clean".
NONEMPTY_IS_REVIEW=1
SECTION_NOTE="Lists only blocks graded C or worse. Empty output means nothing that complex was found."
run_tool "Radon (cyclomatic complexity)"      radon     radon cc -s -n C -e "$EXC" "$TARGET"

NONEMPTY_IS_REVIEW=1
SECTION_NOTE="Lists only files below maintainability grade A. Empty output means every file is A."
run_tool "Radon (maintainability index)"      radon     radon mi -s -n B -e "$EXC" "$TARGET"

NONEMPTY_IS_REVIEW=1
SECTION_NOTE="Raised to 80% minimum confidence. At the 60% default, constant registries and dynamically-referenced names dominate the output and drown the real findings."
run_tool "Vulture (dead code)"                vulture   vulture "$TARGET" --exclude "$EXC" --min-confidence 80

# Tests are excluded: pytest's bare `assert` trips B101 once per assertion, and
# on any real suite that single rule outnumbers every genuine finding by an
# order of magnitude. Severity is NOT filtered — a --severity-level flag would
# suppress Low findings from detection entirely, not just from a summary count,
# silently losing real (if lower-priority) findings from the raw output too.
BANDIT_EXC="${EXC},*/tests/*,*/test/*,*/test_*.py,*_test.py,*/conftest.py"
pick_tool bandit
SECTION_NOTE="${SECTION_NOTE:+$SECTION_NOTE }Test files excluded (bare \`assert\` trips B101 on every line and buries real findings). Drop BANDIT_EXC in the script to include them."
run_tool "Bandit (security)"    "$TOOL_BIN" "${TOOL_CMD[@]}" -r "$TARGET" -x "$BANDIT_EXC"

# Auditing the ambient environment answers a question nobody asked: it
# reports on whatever happens to be installed on this machine, not on what
# the project pins. Prefer requirements.txt, then the uv lockfile exported to
# the same format. Only fall back to the environment when there's nothing to
# read from.
run_pip_audit() {
  local req
  if [ -f "$TARGET/requirements.txt" ]; then
    pip-audit -r "$TARGET/requirements.txt"
  elif [ -f "$TARGET/uv.lock" ] && command -v uv >/dev/null 2>&1; then
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
  SECTION_NOTE="Audited the project's uv.lock (exported to requirements format, runtime deps only) — what the project actually pins, not what's installed on this machine."
else
  SECTION_NOTE="No requirements.txt or uv.lock found. This audited the active Python environment, not the project's pinned deps — treat a clean result as unproven."
fi
run_tool "pip-audit (dependency CVEs)"      pip-audit run_pip_audit

# deptry resolves its dependency spec from CWD and needs a real [project],
# [tool.poetry], or [tool.pdm] table. A uv *virtual workspace* root has none
# — it only lists members — so pointing deptry at the root aborts the whole
# check with DependencySpecificationNotFoundError. Fall back to running it
# once per member that does declare dependencies.
has_dep_spec() { grep -qE '^\[(project\]|tool\.poetry|tool\.pdm)' "$1/pyproject.toml" 2>/dev/null; }
# deptry maps a distribution name to its import name by introspecting the
# installed package. With nothing installed it guesses from the name, and
# every package whose import name differs from its distribution name
# (python-jose -> jose, PyYAML -> yaml, google-cloud-* -> google) becomes a
# false DEP001 "imported but missing". Running it inside the project's own
# uv environment removes that entire class of noise, so prefer that.
deptry_in() {
  local dir="$1"
  if command -v uv >/dev/null 2>&1 && [ -f "$dir/pyproject.toml" ]; then
    ( cd "$dir" && uv run --project . --with deptry -- deptry . --exclude "$DEPTRY_EXC" )
  else
    ( cd "$dir" && deptry . --exclude "$DEPTRY_EXC" )
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
  run_tool "deptry (dependency hygiene)"      deptry    run_deptry
else
  FORCE_SKIP="No pyproject.toml, requirements.txt, or setup.py in the target. deptry needs a declared dependency spec to run."
  run_tool "deptry (dependency hygiene)"      deptry    run_deptry
fi

# --- git history (informational: where change and knowledge concentrate) ---
if git -C "$TARGET" rev-parse >/dev/null 2>&1; then
  INFO_SECTION=1
  SECTION_NOTE="Most-changed files in the last 12 months. Cross-reference with the complexity output: high churn + high complexity is your highest-risk code."
  run_tool "Churn hotspots (git)"             git       churn_hotspots

  INFO_SECTION=1
  SECTION_NOTE="Files touched by only one author. These are knowledge silos and onboarding risk. Empty output is good news."
  run_tool "Bus factor (git)"                 git       bus_factor

  INFO_SECTION=1
  SECTION_NOTE="Files appearing most in fix/bug commits over 24 months. Repeated fixes signal structural weakness."
  run_tool "Bug-fix clusters (git)"           git       bugfix_clusters
else
  FORCE_SKIP="Target is not a git repository, so history-based signals are unavailable."
  run_tool "Git history"                      git       true
fi

# --- context for the header ---
py_count="$(find "$TARGET" -type f -name '*.py' \
  -not -path '*/.git/*' -not -path '*/.venv/*' -not -path '*/venv/*' \
  -not -path '*/node_modules/*' -not -path '*/build/*' -not -path '*/dist/*' \
  -not -path '*/migrations/*' -not -name '*_generated.py' -not -name '*_pb2.py' 2>/dev/null | wc -l | tr -d ' ')"
sh_count="$(find "$TARGET" -type f -name '*.sh' \
  -not -path '*/.git/*' -not -path '*/.venv/*' -not -path '*/venv/*' \
  -not -path '*/node_modules/*' -not -path '*/build/*' -not -path '*/dist/*' \
  -not -path '*/migrations/*' 2>/dev/null | wc -l | tr -d ' ')"

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

  printf '## Summary\n\n'
  printf '| Check | Status | Exit | Time |\n'
  printf '|---|---|---|---|\n'
  cat "$SUMMARY"
  printf '\n'
  printf 'Status legend: `clean` exit 0, no findings. `review` nonzero exit, '
  printf 'findings or a tool error worth reading. `info` informational output '
  printf '(git history), not pass/fail. `skipped` tool unavailable or not applicable.\n\n'
  printf 'Nonzero exits are expected when a tool finds something and do not mean the run failed.\n\n'

  printf '## Details\n\n'
  cat "$DETAILS"
} >"$REPORT"

echo >&2
echo "Report: $REPORT" >&2
echo "Raw logs: $RAW/" >&2
printf '%s\n' "$REPORT"
