> **Status:** Reference — ground truth for a reviewer-benchmark case.

# A — secret file permissions

**Source:** `git diff 9e33ca4..bf73170` (the state reviewed on PR #235 before the fix).

**The defect a reviewer must find:**

`_write_0600` opens with `os.open(path, ..., 0o600)`. That mode argument applies
**only when the file is created**. An existing file at 0644 is truncated and
rewritten at 0644, so the *replacement* key material is on disk world-readable
until the trailing `chmod`. The fix is `os.fchmod` on the descriptor before any
bytes are written.

**Credit also for:** noting that a path-based `os.chmod` re-resolves the name, so
a symlink swapped in between write and chmod redirects the permission change.

**Not the answer:** "the code writes secrets with 0600" (it does, on creation);
anything about the `jackpot_evidence.py` directory modes, which are correct here.

**Why it is a good case:** requires knowing a POSIX detail that is invisible from
reading the diff in isolation, and the surrounding comment claims the window is
already handled — so a reviewer that trusts comments fails.
