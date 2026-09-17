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
| `gemma4:31b` | 0 / 3 | restated the diff; timed out on C | >3 min/case |
| `kimi-k2.7-code:cloud` | untested | — | 402, needs Ollama credits |
| `glm-5.2:cloud` | untested | — | 402, needs Ollama credits |

CodeRabbit set the bar by finding all three **in fixes written by the agent** —
B and C were defects introduced while fixing something else.

The four false positives on case C are worth reading in
`C_exception_breadth.expected.md`: one of them ("SQL injection via
`(:days || ' days')::INTERVAL`") is confident, plausible, and wrong, because
`:days` is a bound parameter. That is the expensive kind.

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
