> **Status:** Reference — scoring harness for candidate code reviewers.

# Reviewer benchmark

Three real diffs from this repository, each containing one defect that was found
in review and confirmed by fixing it. Use them to answer "is reviewer X worth
adding to the loop?" by measurement rather than argument.

Every case is a **pre-fix state from a merged PR**, so the answers are not
hypothetical: each defect was real enough to warrant its own commit.

| case | defect | PR |
|---|---|---|
| A | `os.open(…, 0o600)` does not narrow an **existing** file | #235 |
| B | an account that must not be in an IAM `actAs` set | #244 |
| C | `except IntegrityError` too broad — the table has three FKs | #248 |

They were chosen because each defeats a different shortcut. A rewards knowing a
POSIX detail the diff does not state, and punishes trusting a nearby comment that
claims the window is handled. B hides a one-line widening *inside* a security
improvement, so scoring the overall direction fails it. C separates reviewers
that reason about this schema from ones that pattern-match on `except` blocks.

## What this measures — and what it does not

**Diff review with no repo context.** Each case is a diff fragment; the reviewer
does not get the surrounding file. That is deliberate — it is the job CodeRabbit
does in the PR loop — but it makes the benchmark unfair to tools built for a
different job, and a low score here must not be read as "this reviewer is bad".

The clearest example is in the table below. `qwen3-coder:30b` scores 0/3 on diff
review, and is also the model behind `code_check_opencode.sh`, which reviews one
**whole file at a time with full content** — and that scan produced the report
that drove roughly nineteen PRs of real fixes. Same model, opposite verdicts,
because whole-file scanning and diff review are different tasks. Case C needed to
know the table has three foreign keys; case A needed to know the file already
existed. Neither fact is in the diff.

So: use this to choose a **diff reviewer**. To judge a whole-file scanner, build
a second case set from pre-existing defects with full files, and score recall —
a scanner may earn its place at 50% precision if triage is cheap, where a diff
reviewer at 50% precision mostly wastes the reviewer's time.

## Running

```bash
docs/reviewer_benchmark/run.sh 'ollama run qwen3-coder:30b'
```

The command reads a prompt on stdin and writes its review to stdout. Then read
each `cases/*.expected.md` and decide whether the reviewer found **the** defect.

Scoring is manual on purpose. A reviewer that lists ten plausible issues and
misses the one that matters has failed the case, and automating that judgement
needs a judge as good as the thing being judged. Count false positives too: they
are not free, because each one costs someone the time to disprove it.

## Results so far

| reviewer | found | false positives | speed |
|---|---|---|---|
| CodeRabbit CLI | **3 / 3** | 0 | 2–4 min, rate-limited at 3 runs |
| `qwen3-coder:30b` | 0 / 3 | 4 on case C, all wrong on inspection | ~12 s/case |

`qwen3-coder:30b`'s 0/3 is a statement about diff review only — see the section
above. The same model, given whole files, generated the report behind ~19 merged
PRs of confirmed fixes.
| `gemma4:31b` | 0 / 3 | restated the diff; timed out on C | >3 min/case |
| `kimi-k2.7-code:cloud` | untested | — | 402, needs Ollama credits |
| `glm-5.2:cloud` | untested | — | 402, needs Ollama credits |

CodeRabbit set the bar by finding all three **in fixes written by the agent** —
B and C were defects introduced while fixing something else.

The four false positives on case C are worth reading in
`C_exception_breadth.expected.md`: one of them ("SQL injection via
`(:days || ' days')::INTERVAL`") is confident, plausible, and wrong, because
`:days` is a bound parameter. That is the expensive kind.

## A failure mode this benchmark cannot see

The scanner it is contrasted with had a defect that no score would have caught:
`code_check_opencode.sh` passed files as `@path`, which makes opencode hand the
model a `read` **tool**. `qwen3-coder:30b` cannot emit valid tool-call syntax, so
the read never executed — the output stopped after a malformed `<function=read>`
and the file was never reviewed. **21 of 167 outputs in the 2026-08-04 scan
failed this way**, invisibly, because a stub looks like any other file in a
directory of 167.

Fixed by inlining file content instead of referencing it, plus a completion
check that greps each output for leaked tool-call syntax and reports
`incomplete: N` at the end. Verified on an 84 KB file that previously failed: it
now produces a real review citing functions from its *tail*.

The lesson generalises past this script. **A reviewer that cannot read the code
produces output that looks like a review.** Any harness that runs one has to
assert the read happened, not just that the process exited zero.

## Operational notes

Local models are resource-bound in a way that looks like a bad score. Midway
through the run that produced the table above, `qwen3-coder:30b` sat resident at
21 GB with a 32k context and stopped answering inside two minutes, while
`qwen2.5-coder:1.5b` still replied instantly. Check `ollama ps` before
concluding a reviewer found nothing — an empty answer from a loaded 30B is more
likely to be memory pressure than a verdict.

`OLLAMA_CONTEXT_LENGTH` is exported by `run.sh` because Ollama otherwise
truncates at its default and **says nothing**. A silently truncated diff produces
a confident review of a fragment, which is the failure this whole benchmark
exists to detect.

## Adding a case

Take a defect that review actually caught, before the fix:

```bash
git diff <base>..<pre-fix-commit> -- <paths> > cases/D_thing.diff
```

Write `cases/D_thing.expected.md` with the defect, what else deserves credit,
and — most usefully — the plausible wrong answers, so the next person can tell a
near-miss from a hit.

Prefer defects that were **found in a fix**, not in original code. Those are the
ones where a second opinion earns its keep, and they are the cases a reviewer
optimised for "looks reasonable" will fail.
