#!/usr/bin/env bash
# scripts/srt_selftest.sh — verify srt actually constrains what the settings claim.
# Run after every srt upgrade. A sandbox you have not verified is a sandbox you do not have.
set -uo pipefail
S=$(mktemp /tmp/srt-selftest.XXXXXX.json)
python3 scripts/srt_settings.py "$PWD" > "$S"
fail=0

if srt --settings "$S" -- curl -s -m 5 https://example.com >/dev/null 2>&1; then
  echo "FAIL: reached a domain that is not on the allowlist (sandbox failing open)"; fail=1
else
  echo "ok: non-allowlisted domain blocked"
fi

if srt --settings "$S" -- curl -s -m 15 https://pypi.org/simple/ >/dev/null 2>&1; then
  echo "ok: allowlisted domain reachable"
else
  echo "FAIL: allowlisted domain unreachable (settings malformed or schema changed)"; fail=1
fi

if srt --settings "$S" -- touch "$HOME/.srt-escape-test" 2>/dev/null; then
  echo "FAIL: wrote outside the worktree"; rm -f "$HOME/.srt-escape-test"; fail=1
else
  echo "ok: write outside the worktree blocked"
fi

rm -f "$S"
[ "$fail" -eq 0 ] && echo "srt self-test passed." || echo "srt self-test FAILED. Do not run agents unattended."
exit "$fail"
