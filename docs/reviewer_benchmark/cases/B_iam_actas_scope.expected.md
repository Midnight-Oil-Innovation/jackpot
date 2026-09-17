> **Status:** Reference — ground truth for a reviewer-benchmark case.

# B — IAM actAs scoping

**Source:** `git diff 73dcc73..b2eee9d` (the state reviewed on PR #244 before the fix).

**The defect a reviewer must find:**

The diff narrows `roles/iam.serviceAccountUser` from project level to a named set
of accounts — correct in direction, but the set **includes the scrubber service
account**. That account exists for SRA Human Scrubber GKE Jobs, which run under
Workload Identity and need no `actAs` from the API. Including it lets a
compromised API pod run arbitrary Batch workloads as the account that reads
*unscrubbed* data — the exact widening the change exists to remove.

**Not the answer:** praising the project-level → resource-level narrowing (that
part is right); anything about `data.google_project` being used for the project
number (also right).

**Why it is a good case:** the diff is a security *improvement*, and the defect is
one line inside it. A reviewer that scores the overall direction misses it.
