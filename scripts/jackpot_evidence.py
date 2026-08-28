#!/usr/bin/env python3
"""jackpot_evidence.py

Working-tree-bound verification evidence ledger.

Records that a command (typically a test lane) ran against a specific content
state of the working tree, then grades that evidence FRESH, STALE, or MISSING
later. Evidence is bound to a git content fingerprint, not a commit SHA, so it
survives commits, amends, rebases, and squashes as long as the bytes on disk
are unchanged, and goes STALE the moment they change.

The fingerprint is a git tree object id computed over the current working tree
(tracked files with local modifications, plus untracked non-ignored files;
gitignored scratch is excluded). Identical content fingerprints identically
across commits and across worktrees of the same repo.

Intended use in the autoloop: the harness wraps its grading run with
`run --label test`, and the human-review gate calls `check --label test` and
refuses to proceed unless it prints FRESH. That turns "the agent says tests
passed" into "tests passed against exactly the tree on disk right now."

Stdlib only. Python 3.12. Safe inside git worktrees. No third-party deps, so
it does not touch the dependency license gate.

Commands:
  fingerprint [--paths P ...]
  run   --label L [--paths P ...] -- <command ...>
  check --label L [--expect-cmd C] [--max-age SECONDS] [--paths P ...]
  list  [--label L] [-n N]

Exit codes for `check`: 0 FRESH, 1 STALE, 3 MISSING. `run` passes the wrapped
command's exit code through unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1
LOG_CAP_BYTES = 2 * 1024 * 1024
LOG_RETENTION_DAYS = 30
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

EXIT_FRESH = 0
EXIT_STALE = 1
EXIT_MISSING = 3


def _git(args, *, index_file=None, check=True):
    env = os.environ.copy()
    if index_file is not None:
        env["GIT_INDEX_FILE"] = index_file
    result = subprocess.run(["git", *args], env=env, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result


def repo_root() -> Path:
    return Path(_git(["rev-parse", "--show-toplevel"]).stdout.strip())


def git_head() -> str:
    r = _git(["rev-parse", "HEAD"], check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def git_branch() -> str:
    r = _git(["branch", "--show-current"], check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def working_tree_fingerprint(paths=None) -> str:
    """Return a git tree object id for the current working-tree content.

    Builds a throwaway index from scratch so the real index and stat cache are
    never touched, stages everything (respecting .gitignore), and writes the
    tree. Blobs written to the object store are content-addressed and harmless;
    routine `git gc` reclaims any that never get referenced.
    """
    fd, tmp = tempfile.mkstemp(prefix="jackpot-wtidx-")
    os.close(fd)
    # git needs to create a fresh, valid index; an empty 0-byte file is not one.
    os.unlink(tmp)
    try:
        add_args = ["add", "-A"]
        if paths:
            add_args += ["--", *paths]
        _git(add_args, index_file=tmp)
        return _git(["write-tree"], index_file=tmp).stdout.strip()
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def state_root() -> Path:
    override = os.environ.get("JACKPOT_STATE_ROOT")
    base = Path(override) if override else repo_root() / ".jackpot"
    return base / "evidence"


def ledger_path() -> Path:
    return state_root() / "ledger.jsonl"


def logs_dir() -> Path:
    return state_root() / "logs"


def _ensure_dirs():
    root = state_root()
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    logs = logs_dir()
    logs.mkdir(parents=True, exist_ok=True)
    os.chmod(logs, 0o700)


def _prune_logs():
    cutoff = time.time() - LOG_RETENTION_DAYS * 86400
    if not logs_dir().exists():
        return
    for f in logs_dir().glob("*.log"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


def append_record(record: dict):
    _ensure_dirs()
    with open(ledger_path(), "a") as fh:
        fh.write(json.dumps(record, separators=(",", ":")) + "\n")


def iter_records():
    path = ledger_path()
    if not path.exists():
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def latest_record(label: str):
    found = None
    for rec in iter_records():
        if rec.get("label") == label:
            found = rec
    return found


def cmd_fingerprint(args) -> int:
    print(working_tree_fingerprint(args.paths))
    return 0


def cmd_run(args) -> int:
    if not args.command:
        print("error: no command given after --", file=sys.stderr)
        return 2
    _ensure_dirs()
    _prune_logs()

    paths = args.paths or None
    pre = working_tree_fingerprint(paths)
    started = datetime.now(UTC)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    log_file = logs_dir() / f"{args.label}-{stamp}.log"

    written = 0
    truncated = False
    proc = subprocess.Popen(
        args.command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    fd = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as log:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            if written < LOG_CAP_BYTES:
                log.write(line)
                written += len(line.encode("utf-8", "replace"))
                if written >= LOG_CAP_BYTES:
                    log.write("\n[jackpot_evidence: log truncated at cap]\n")
                    truncated = True
    returncode = proc.wait()

    duration = (datetime.now(UTC) - started).total_seconds()
    post = working_tree_fingerprint(paths)

    record = {
        "schema_version": SCHEMA_VERSION,
        "label": args.label,
        "cmd": list(args.command),
        "cmd_str": shlex.join(args.command),
        "paths": list(paths) if paths else [],
        "pre_fingerprint": pre,
        "post_fingerprint": post,
        "mutated_tree": pre != post,
        "exit_code": returncode,
        "started_at": started.isoformat(),
        "duration_s": round(duration, 3),
        "git_head": git_head(),
        "git_branch": git_branch(),
        "log": str(log_file.relative_to(state_root())),
        "log_truncated": truncated,
    }
    append_record(record)

    if pre != post:
        print(
            "jackpot_evidence: warning: command mutated the working tree "
            f"({pre[:12]} -> {post[:12]}); evidence is bound to the pre-run "
            "state.",
            file=sys.stderr,
        )
    return returncode


def _age_seconds(iso_ts: str) -> float:
    started = datetime.fromisoformat(iso_ts)
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return (datetime.now(UTC) - started).total_seconds()


def cmd_check(args) -> int:
    rec = latest_record(args.label)
    if rec is None:
        print(f"MISSING  {args.label}  (no evidence recorded)")
        return EXIT_MISSING

    # Recompute the fingerprint on the same path basis the record used, unless
    # the caller explicitly overrides. Comparing across different path bases
    # would be meaningless.
    if args.paths is not None:
        paths = args.paths or None
        basis = "override"
    else:
        paths = rec.get("paths") or None
        basis = "recorded"
    current = working_tree_fingerprint(paths)

    reasons = []
    if rec.get("exit_code", 1) != 0:
        reasons.append(f"recorded run failed (exit {rec.get('exit_code')})")
    if rec.get("pre_fingerprint") != current:
        reasons.append("working tree changed since evidence")
    if args.expect_cmd is not None and rec.get("cmd_str") != args.expect_cmd:
        reasons.append(f"command mismatch (recorded: {rec.get('cmd_str')!r})")
    age = _age_seconds(rec["started_at"])
    if args.max_age is not None and age > args.max_age:
        reasons.append(f"evidence age {int(age)}s exceeds max-age {args.max_age}s")

    label = args.label
    fp = current[:12]
    if not reasons:
        print(
            f"FRESH    {label}  tree={fp}  age={int(age)}s  "
            f"cmd={rec.get('cmd_str')}  (basis: {basis})"
        )
        return EXIT_FRESH

    print(f"STALE    {label}  tree={fp}  age={int(age)}s  (basis: {basis})")
    for r in reasons:
        print(f"         - {r}")
    return EXIT_STALE


def cmd_list(args) -> int:
    records = [r for r in iter_records() if args.label is None or r.get("label") == args.label]
    if not records:
        print("(no evidence records)")
        return 0
    for rec in records[-args.n :]:
        status = "ok" if rec.get("exit_code") == 0 else f"exit {rec.get('exit_code')}"
        print(
            f"{rec.get('started_at')}  {rec.get('label'):<12}  "
            f"tree={rec.get('pre_fingerprint', '')[:12]}  {status:<8}  "
            f"{rec.get('duration_s')}s  {rec.get('cmd_str')}"
        )
    return 0


def _split_command_argv(argv):
    """Split argv on the first standalone -- into (parser_args, command)."""
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1 :]
    return argv, []


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="jackpot_evidence",
        description="Working-tree-bound verification evidence ledger.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    fp = sub.add_parser("fingerprint", help="print the working-tree fingerprint")
    fp.add_argument(
        "--paths", nargs="*", default=None, help="restrict the fingerprint to these pathspecs"
    )
    fp.set_defaults(func=cmd_fingerprint)

    rn = sub.add_parser("run", help="run a command and record evidence")
    rn.add_argument("--label", required=True, help="evidence lane, e.g. test")
    rn.add_argument(
        "--paths", nargs="*", default=None, help="bind evidence to these pathspecs only"
    )
    rn.set_defaults(func=cmd_run)

    ck = sub.add_parser("check", help="grade the latest evidence for a lane")
    ck.add_argument("--label", required=True)
    ck.add_argument(
        "--expect-cmd", default=None, help="require the recorded command to equal this string"
    )
    ck.add_argument(
        "--max-age", type=int, default=None, help="fail if evidence is older than this many seconds"
    )
    ck.add_argument(
        "--paths", nargs="*", default=None, help="override the path basis for the freshness check"
    )
    ck.set_defaults(func=cmd_check)

    ls = sub.add_parser("list", help="show recent evidence records")
    ls.add_argument("--label", default=None)
    ls.add_argument("-n", type=int, default=10)
    ls.set_defaults(func=cmd_list)

    return p


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    head, command = _split_command_argv(argv)
    parser = build_parser()
    args = parser.parse_args(head)
    if args.cmd == "run":
        args.command = command
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
