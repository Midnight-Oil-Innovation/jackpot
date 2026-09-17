#!/usr/bin/env bash
# Score a candidate code reviewer against cases with known answers.
#
#   ./run.sh 'ollama run qwen3-coder:30b'
#   ./run.sh 'ollama run kimi-k2.7-code:cloud'
#
# The command must read a prompt on stdin and write its review to stdout.
# Scoring is deliberately manual: read each case's .expected.md and decide
# whether the reviewer found THE defect. A reviewer that lists ten plausible
# issues and misses the one that matters has failed the case — automating that
# judgement would need a judge as good as the thing being judged.
set -euo pipefail

cmd="${1:-}"
if [ -z "$cmd" ]; then
  echo "usage: $0 '<command that reads a prompt on stdin>'" >&2
  exit 2
fi

cd "$(dirname "$0")"

# Ollama truncates silently at its default context. The largest case is well
# under this; raise it if you add a bigger one.
export OLLAMA_CONTEXT_LENGTH="${OLLAMA_CONTEXT_LENGTH:-8192}"

prompt='You are reviewing a code diff for correctness and security defects.
Report only concrete defects in the changed code, each on one line as:
SEVERITY | file | what is wrong. If you find none, say NONE.
Do not restate what the diff does.'

for diff in cases/*.diff; do
  case_name="$(basename "$diff" .diff)"
  echo "=============================================================="
  echo "CASE: $case_name"
  echo "expected: cases/${case_name}.expected.md"
  echo "--------------------------------------------------------------"
  # No `</dev/null` here: it would override the pipe and hand the reviewer an
  # empty prompt, which scores every candidate 0/3 for the wrong reason.
  printf '%s\n\n```diff\n%s\n```\n' "$prompt" "$(cat "$diff")" \
    | eval "$cmd" 2>/dev/null \
    | tr -d '\r' | sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g' | grep -v '^$'
  echo
done
