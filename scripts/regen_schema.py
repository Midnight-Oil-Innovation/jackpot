#!/usr/bin/env python3
"""
regen_schema.py — Regenerate JACKPOT's auto-generated schema artifacts from
the LinkML YAML source of truth.

Bundles four steps into one command:
    1. Regenerate `backend/backend/models_generated.py` via `gen-pydantic`
    2. Apply Critical Rule 20 patches (boolean keyword fix + trailing newline)
    3. Regenerate `schema/schema/jackpot_schema.json` via `gen-json-schema`
    4. Verify both artifacts parse / import cleanly

USAGE:
    # Default: regenerate both files in place
    python3 scripts_jackpot/regen_schema.py

    # Check-only mode: regenerate to /tmp, compare against committed files,
    # exit 0 if no drift, exit 1 if drift detected (suitable for CI / pre-commit)
    python3 scripts_jackpot/regen_schema.py --check

    # Quieter output
    python3 scripts_jackpot/regen_schema.py --quiet

    # Override repo root (default: auto-detected from script location)
    python3 scripts_jackpot/regen_schema.py --repo /path/to/jackpot

EXIT CODES:
    0 — success (in-place regen succeeded; or --check found no drift)
    1 — regen step failed, verification failed, or --check found drift
    2 — bad invocation, repo not found, schema YAML missing
"""

from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# Paths relative to repo root
SCHEMA_YAML_REL = "schema/schema/jackpot_schema.yaml"
MODELS_PY_REL = "backend/backend/models_generated.py"
SCHEMA_JSON_REL = "schema/schema/jackpot_schema.json"

# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class StepResult:
    name: str
    ok: bool
    message: str = ""
    details: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT HELPERS
# ─────────────────────────────────────────────────────────────────────────────


class Reporter:
    """Tiny reporter — prints progress when not quiet, captures step results."""

    def __init__(self, quiet: bool = False) -> None:
        self.quiet = quiet
        self.results: list[StepResult] = []

    def header(self, text: str) -> None:
        if self.quiet:
            return
        print()
        print("=" * 78)
        print(f"  {text}")
        print("=" * 78)

    def step(self, name: str) -> None:
        if self.quiet:
            return
        print(f"\n→ {name}")

    def ok(self, name: str, message: str = "", details: str = "") -> None:
        self.results.append(StepResult(name=name, ok=True, message=message, details=details))
        if self.quiet:
            return
        line = f"  ✓ {name}"
        if message:
            line += f" — {message}"
        print(line)
        if details and not self.quiet:
            for ln in details.splitlines():
                print(f"    {ln}")

    def fail(self, name: str, message: str, details: str = "") -> None:
        self.results.append(StepResult(name=name, ok=False, message=message, details=details))
        # Failures always print, even in quiet mode
        print(f"  ✗ {name} — {message}", file=sys.stderr)
        if details:
            for ln in details.splitlines():
                print(f"    {ln}", file=sys.stderr)

    def info(self, message: str) -> None:
        if self.quiet:
            return
        print(f"    {message}")

    def all_ok(self) -> bool:
        return all(r.ok for r in self.results)


# ─────────────────────────────────────────────────────────────────────────────
# REPO DETECTION
# ─────────────────────────────────────────────────────────────────────────────


def find_repo_root(starting: Path | None = None) -> tuple[Path | None, list[Path]]:
    """Walk up from candidate locations to find the repo root.
    Recognized by a top-level pyproject.toml with `[tool.uv.workspace]`.

    Tries the script's directory first, then the current working directory.
    Returns (found_root, list_of_directories_checked). If not found, the
    second item lists what was searched so the caller can show a helpful
    error message.
    """
    candidates: list[Path] = []
    if starting is not None:
        candidates.append(starting)
    else:
        candidates.append(Path(__file__).resolve().parent)
        candidates.append(Path.cwd().resolve())

    seen: set[Path] = set()
    checked: list[Path] = []
    for start in candidates:
        current = start
        for _ in range(10):
            if current in seen:
                break
            seen.add(current)
            checked.append(current)
            candidate = current / "pyproject.toml"
            if candidate.is_file():
                try:
                    text = candidate.read_text(encoding="utf-8", errors="replace")
                    if "[tool.uv.workspace]" in text:
                        return current, checked
                except OSError:
                    pass
            if current.parent == current:
                break
            current = current.parent
    return None, checked


# ─────────────────────────────────────────────────────────────────────────────
# STEP IMPLEMENTATIONS
# ─────────────────────────────────────────────────────────────────────────────


# Cap diff output in compare_files() — module-level constant (avoids N806).
MAX_DIFF_LINES = 80


def _display_path(path: Path, repo_root: Path) -> str:
    """Return ``path`` rendered relative to ``repo_root`` if possible, else absolute.
    Used purely for human-readable progress output — never for filesystem ops."""
    if path.is_relative_to(repo_root):
        return str(path.relative_to(repo_root))
    return str(path)


def run_subprocess(
    cmd: list[str],
    repo_root: Path,
    output_path: Path | None = None,
    suppress_dep_warning: bool = True,
) -> tuple[bool, str, str]:
    """Run a subprocess command, capturing stdout/stderr.

    If `output_path` is given, stdout is written there instead of being captured.
    Returns (ok, stdout_or_stderr_summary, full_stderr).
    """
    env = None
    if suppress_dep_warning:
        # Silence the noisy `RequestsDependencyWarning` that gen-json-schema emits
        # without affecting other warnings.
        import os

        env = os.environ.copy()
        existing = env.get("PYTHONWARNINGS", "")
        injected = "ignore::requests.exceptions.RequestsDependencyWarning"
        env["PYTHONWARNINGS"] = f"{injected},{existing}" if existing else injected

    try:
        if output_path is not None:
            with open(output_path, "wb") as outf:
                proc = subprocess.run(
                    cmd,
                    cwd=repo_root,
                    stdout=outf,
                    stderr=subprocess.PIPE,
                    env=env,
                    check=False,
                )
            stderr_text = proc.stderr.decode("utf-8", errors="replace")
            return (
                proc.returncode == 0,
                f"wrote {_display_path(output_path, repo_root)}",
                stderr_text,
            )
        else:
            proc = subprocess.run(
                cmd,
                cwd=repo_root,
                capture_output=True,
                env=env,
                check=False,
            )
            stdout_text = proc.stdout.decode("utf-8", errors="replace")
            stderr_text = proc.stderr.decode("utf-8", errors="replace")
            return (proc.returncode == 0, stdout_text, stderr_text)
    except FileNotFoundError as e:
        return (False, "", f"command not found: {e}")
    except OSError as e:
        return (False, "", f"OSError: {e}")


def step_validate_yaml(repo_root: Path, reporter: Reporter) -> bool:
    reporter.step("Validate schema YAML parses")
    yaml_path = repo_root / SCHEMA_YAML_REL
    if not yaml_path.is_file():
        reporter.fail("validate-yaml", f"schema YAML not found at {yaml_path}")
        return False
    try:
        # Use the project's own Python so we use the same yaml lib version
        yaml_check_script = (
            f"import yaml; yaml.safe_load(open({str(yaml_path)!r}, encoding='utf-8')); print('ok')"
        )
        ok, stdout, stderr = run_subprocess(
            ["uv", "run", "python", "-c", yaml_check_script],
            repo_root,
        )
        if ok:
            reporter.ok("validate-yaml", "schema YAML parses cleanly")
            return True
        else:
            reporter.fail("validate-yaml", "schema YAML parse error", details=stderr.strip())
            return False
    except (subprocess.CalledProcessError, OSError) as e:
        reporter.fail("validate-yaml", f"unexpected error: {e}")
        return False


def step_gen_pydantic(repo_root: Path, output_path: Path, reporter: Reporter) -> bool:
    reporter.step(f"Generate Pydantic models → {_display_path(output_path, repo_root)}")
    yaml_path = repo_root / SCHEMA_YAML_REL
    cmd = ["uv", "run", "gen-pydantic", "--pydantic-version", "2", str(yaml_path)]
    ok, summary, stderr = run_subprocess(cmd, repo_root, output_path=output_path)
    if not ok:
        reporter.fail("gen-pydantic", "command failed", details=stderr.strip())
        return False
    # Check the file is non-empty
    try:
        size = output_path.stat().st_size
    except OSError as e:
        reporter.fail("gen-pydantic", f"output file unreadable: {e}")
        return False
    if size < 1000:
        reporter.fail(
            "gen-pydantic",
            f"output suspiciously small ({size} bytes)",
            details="gen-pydantic likely produced an error message instead of code",
        )
        return False
    reporter.ok("gen-pydantic", f"{size:,} bytes written")
    return True


def step_apply_boolean_patch(target_path: Path, reporter: Reporter) -> bool:
    """Apply Critical Rule 20 patches + match pre-commit-hook formatting.

    Three transformations:
      1. Boolean-keyword fix: ``True``/``False`` → ``true``/``false`` in enum
         members (Critical Rule 20).
      2. Trailing-whitespace strip per line. ``gen-pydantic`` emits blank
         lines with indentation whitespace inside enum classes; the
         pre-commit ``trailing-whitespace`` hook strips them on commit, so
         the committed file ends up with bare ``\\n`` while a fresh regen
         would produce ``    \\n``. Without this strip every regen drifts.
      3. Single trailing newline at end of file.
    """
    reporter.step(f"Apply boolean-keyword + format patches → {target_path.name}")
    try:
        content = target_path.read_text(encoding="utf-8")
    except OSError as e:
        reporter.fail("boolean-patch", f"cannot read target: {e}")
        return False

    # Track substitutions for visibility
    true_count = content.count('\n    True = "True"')
    false_count = content.count('\n    False = "False"')

    # 1. Apply boolean-keyword fix
    patched = content.replace('\n    True = "True"', '\n    true = "True"')
    patched = patched.replace('\n    False = "False"', '\n    false = "False"')

    # 2. Strip trailing whitespace from every line — matches the pre-commit
    #    trailing-whitespace hook behavior so regenerated files stay in
    #    sync with committed files.
    lines_before = patched.split("\n")
    lines_after = [line.rstrip() for line in lines_before]
    trailing_ws_changes = sum(1 for b, a in zip(lines_before, lines_after, strict=True) if b != a)
    patched = "\n".join(lines_after)

    # 3. Normalize: exactly one trailing newline at end of file.
    patched = patched.rstrip("\n") + "\n"

    if patched == content:
        reporter.ok("boolean-patch", "no patches needed (output already clean)")
        return True

    try:
        target_path.write_text(patched, encoding="utf-8")
    except OSError as e:
        reporter.fail("boolean-patch", f"cannot write target: {e}")
        return False

    msgs = []
    if true_count:
        msgs.append(f"True→true ×{true_count}")
    if false_count:
        msgs.append(f"False→false ×{false_count}")
    if trailing_ws_changes:
        msgs.append(f"trailing-ws stripped on {trailing_ws_changes} line(s)")
    if patched.endswith("\n") and not content.endswith("\n"):
        msgs.append("trailing newline added")
    reporter.ok("boolean-patch", ", ".join(msgs) if msgs else "normalized")
    return True


def step_verify_pydantic_imports(target_path: Path, reporter: Reporter) -> bool:
    """Verify the patched Pydantic file imports cleanly via importlib.util."""
    reporter.step("Verify Pydantic models import cleanly")
    try:
        spec = importlib.util.spec_from_file_location("models_generated_check", target_path)
        if spec is None or spec.loader is None:
            reporter.fail("verify-pydantic", "could not build module spec from file")
            return False
        mod = importlib.util.module_from_spec(spec)
        # Suppress requests dep warning if pydantic transitively triggers it
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            spec.loader.exec_module(mod)
    except Exception as e:
        reporter.fail(
            "verify-pydantic",
            f"import failed: {type(e).__name__}: {e}",
            details="The boolean-keyword patch may have missed a True/False enum member. "
            "Inspect the generated file for raw `True =` or `False =` lines.",
        )
        return False
    public_count = sum(1 for x in dir(mod) if not x.startswith("_"))
    reporter.ok("verify-pydantic", f"{public_count} public symbols, imports OK")
    return True


def step_gen_json_schema(repo_root: Path, output_path: Path, reporter: Reporter) -> bool:
    reporter.step(f"Generate JSON Schema → {_display_path(output_path, repo_root)}")
    yaml_path = repo_root / SCHEMA_YAML_REL
    cmd = ["uv", "run", "gen-json-schema", str(yaml_path)]
    ok, summary, stderr = run_subprocess(cmd, repo_root, output_path=output_path)
    if not ok:
        reporter.fail("gen-json-schema", "command failed", details=stderr.strip())
        return False
    try:
        size = output_path.stat().st_size
    except OSError as e:
        reporter.fail("gen-json-schema", f"output file unreadable: {e}")
        return False
    if size < 1000:
        reporter.fail("gen-json-schema", f"output suspiciously small ({size} bytes)")
        return False

    # Normalize trailing whitespace + ensure single trailing newline, mirroring
    # the pre-commit trailing-whitespace + end-of-file hooks. Without this,
    # any whitespace `gen-json-schema` emits on blank lines would get stripped
    # by the hook on commit and the next --check run would false-positive
    # drift on the JSON file. (Same reasoning as the Python boolean-patch
    # step.)
    try:
        json_content = output_path.read_text(encoding="utf-8")
        json_lines = [line.rstrip() for line in json_content.split("\n")]
        json_normalized = "\n".join(json_lines).rstrip("\n") + "\n"
        if json_normalized != json_content:
            output_path.write_text(json_normalized, encoding="utf-8")
            size = output_path.stat().st_size
    except OSError as e:
        reporter.fail("gen-json-schema", f"normalization failed: {e}")
        return False

    reporter.ok("gen-json-schema", f"{size:,} bytes written")
    return True


def step_verify_json(target_path: Path, reporter: Reporter) -> bool:
    reporter.step("Verify JSON Schema parses")
    try:
        with open(target_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        reporter.fail("verify-json", f"parse failed: {e}")
        return False
    if not isinstance(data, dict):
        reporter.fail("verify-json", f"top-level not a dict (got {type(data).__name__})")
        return False
    defs = data.get("$defs") or data.get("definitions") or {}
    reporter.ok("verify-json", f"valid JSON, {len(defs)} top-level definitions")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# CHECK-MODE COMPARISON
# ─────────────────────────────────────────────────────────────────────────────


def compare_files(generated: Path, committed: Path, reporter: Reporter, label: str) -> bool:
    """Return True if files match, False if drift detected."""
    if not committed.is_file():
        reporter.fail(f"compare-{label}", f"committed file does not exist: {committed}")
        return False
    try:
        gen_text = generated.read_text(encoding="utf-8")
        com_text = committed.read_text(encoding="utf-8")
    except OSError as e:
        reporter.fail(f"compare-{label}", f"read failed: {e}")
        return False

    if gen_text == com_text:
        reporter.ok(f"compare-{label}", "no drift")
        return True

    # Build a unified diff for visibility (truncated)
    diff_lines = list(
        difflib.unified_diff(
            com_text.splitlines(keepends=True),
            gen_text.splitlines(keepends=True),
            fromfile=f"committed/{committed.name}",
            tofile=f"regenerated/{generated.name}",
            n=2,
        )
    )
    # MAX_DIFF_LINES is module-level (defined in the STEP IMPLEMENTATIONS section).
    diff_text = "".join(diff_lines[:MAX_DIFF_LINES])
    if len(diff_lines) > MAX_DIFF_LINES:
        diff_text += f"\n... ({len(diff_lines) - MAX_DIFF_LINES} more diff lines)"

    reporter.fail(
        f"compare-{label}",
        f"DRIFT detected ({len(diff_lines)} diff lines)",
        details=diff_text.rstrip(),
    )
    return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATION
# ─────────────────────────────────────────────────────────────────────────────


def regenerate_in_place(repo_root: Path, reporter: Reporter) -> bool:
    """Run the full regen + patch + verify pipeline against the real files."""
    reporter.header("REGENERATING SCHEMA ARTIFACTS")

    if not step_validate_yaml(repo_root, reporter):
        return False

    models_py = repo_root / MODELS_PY_REL
    schema_json = repo_root / SCHEMA_JSON_REL

    # Make sure parent directories exist (they should, but defensive)
    models_py.parent.mkdir(parents=True, exist_ok=True)
    schema_json.parent.mkdir(parents=True, exist_ok=True)

    if not step_gen_pydantic(repo_root, models_py, reporter):
        return False
    if not step_apply_boolean_patch(models_py, reporter):
        return False
    if not step_verify_pydantic_imports(models_py, reporter):
        return False
    if not step_gen_json_schema(repo_root, schema_json, reporter):
        return False
    return step_verify_json(schema_json, reporter)


def regenerate_in_check_mode(repo_root: Path, reporter: Reporter) -> bool:
    """Regenerate to /tmp, then compare against the committed files."""
    reporter.header("CHECK MODE — regenerating to /tmp and diffing")

    if not step_validate_yaml(repo_root, reporter):
        return False

    with tempfile.TemporaryDirectory(prefix="jackpot_regen_") as tmpdir:
        tmp_path = Path(tmpdir)
        tmp_models = tmp_path / "models_generated.py"
        tmp_json = tmp_path / "jackpot_schema.json"

        if not step_gen_pydantic(repo_root, tmp_models, reporter):
            return False
        if not step_apply_boolean_patch(tmp_models, reporter):
            return False
        if not step_verify_pydantic_imports(tmp_models, reporter):
            return False
        if not step_gen_json_schema(repo_root, tmp_json, reporter):
            return False
        if not step_verify_json(tmp_json, reporter):
            return False

        # Compare against committed
        committed_models = repo_root / MODELS_PY_REL
        committed_json = repo_root / SCHEMA_JSON_REL

        models_match = compare_files(
            tmp_models, committed_models, reporter, label="models_generated.py"
        )
        json_match = compare_files(tmp_json, committed_json, reporter, label="jackpot_schema.json")

        return models_match and json_match


def print_summary(reporter: Reporter, mode: str) -> None:
    print()
    print("=" * 78)
    if reporter.all_ok():
        if mode == "check":
            print("  ✓ CHECK PASSED — committed schema artifacts match the YAML source.")
        else:
            print("  ✓ REGEN COMPLETE — schema artifacts up to date with YAML source.")
    else:
        failed = [r for r in reporter.results if not r.ok]
        if mode == "check":
            print(f"  ✗ CHECK FAILED — {len(failed)} step(s) failed or detected drift.")
            print("    Run without --check to update the committed files.")
        else:
            print(f"  ✗ REGEN FAILED — {len(failed)} step(s) failed.")
        for r in failed:
            print(f"    - {r.name}: {r.message}")
    print("=" * 78)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate JACKPOT's auto-generated schema artifacts from the LinkML YAML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "repo_positional",
        nargs="?",
        default=None,
        metavar="REPO",
        help="Repo root (positional shorthand). Equivalent to --repo. "
        "Use '.' to mean current directory.",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Path to repo root (default: auto-detect, looking at "
        "script-dir and CWD for a pyproject.toml with [tool.uv.workspace])",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Regenerate to /tmp and diff against committed files. "
        "Exit 0 if no drift, exit 1 if drift detected. "
        "Suitable for CI / pre-commit.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print only failures and the final summary.",
    )

    args = parser.parse_args(argv)

    # Resolve repo root: positional and --repo are mutually exclusive
    if args.repo and args.repo_positional:
        print("ERROR: pass repo path as positional OR --repo, not both.", file=sys.stderr)
        return 2

    explicit_repo = args.repo or args.repo_positional
    if explicit_repo:
        repo_root = Path(explicit_repo).expanduser().resolve()
        if not repo_root.is_dir():
            print(f"ERROR: {repo_root} is not a directory", file=sys.stderr)
            return 2
        if not (repo_root / "pyproject.toml").is_file():
            print(f"ERROR: {repo_root} does not contain a pyproject.toml", file=sys.stderr)
            return 2
    else:
        repo_root, checked = find_repo_root()
        if repo_root is None:
            print("ERROR: could not auto-detect repo root.", file=sys.stderr)
            print(
                "       Looked for a pyproject.toml containing [tool.uv.workspace] in:",
                file=sys.stderr,
            )
            for d in checked:
                marker = ""
                pt = d / "pyproject.toml"
                if pt.is_file():
                    marker = "  (has pyproject.toml but no [tool.uv.workspace])"
                print(f"         - {d}{marker}", file=sys.stderr)
            print(
                "       Pass the repo path explicitly: regen_schema.py /path/to/repo",
                file=sys.stderr,
            )
            return 2

    # Sanity check: schema YAML must exist
    if not (repo_root / SCHEMA_YAML_REL).is_file():
        print(f"ERROR: schema YAML not found at {repo_root / SCHEMA_YAML_REL}", file=sys.stderr)
        return 2

    # Sanity check: `uv` must be available
    if shutil.which("uv") is None:
        print(
            "ERROR: `uv` not found on PATH. Install uv first or activate the right env.",
            file=sys.stderr,
        )
        return 2

    reporter = Reporter(quiet=args.quiet)
    if not args.quiet:
        print(f"Repo:   {repo_root}")
        print(f"Mode:   {'CHECK (diff-only, no writes)' if args.check else 'REGEN (in-place)'}")

    if args.check:
        success = regenerate_in_check_mode(repo_root, reporter)
        print_summary(reporter, mode="check")
    else:
        success = regenerate_in_place(repo_root, reporter)
        print_summary(reporter, mode="regen")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
