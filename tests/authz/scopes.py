"""Shared canonical scope fixtures for the M0/M1 suites (§3.1.1, ADR 0015).

One rooted path per deployment, built from database ids. The §9 examples'
names become numbers, and — because a scope is derived from real lineage rows
rather than stored (ADR 0015) — **the ids describe a legal database state**:
``labs.id`` and ``samples.id`` are globally unique SERIAL keys, so a lab
belongs to exactly one org and no sample id repeats. The earlier string
fixtures put lab 1 under four different orgs, which no query could ever
produce; deriving the scopes from rows is what caught it.

    org 1  "acme"   — lab 1 (project 2, sample 3), lab 2 (project 9, sample 7)
    org 2  "rival"  — lab 3 (project 4, sample 11)
    org 11 "trap"   — lab 4 (project 5, sample 12)   segment-boundary vs org 1
    org 9  "wwdb"   — lab 5 (project 6, sample 13)
"""

from backend.authz.scope import scope_sql, scope_uri

INSTANCE = scope_uri()
ACME = scope_uri(org=1)
ACME_LAB1 = scope_uri(org=1, lab=1)
ACME_L1_SAMPLE = scope_uri(org=1, lab=1, project=2, sample=3)
ACME_L2_SAMPLE = scope_uri(org=1, lab=2, project=9, sample=7)
RIVAL_SAMPLE = scope_uri(org=2, lab=3, project=4, sample=11)
TRAP_SAMPLE = scope_uri(org=11, lab=4, project=5, sample=12)
WWDB = scope_uri(org=9)
WWDB_SAMPLE = scope_uri(org=9, lab=5, project=6, sample=13)

FIXTURE_SCOPES = [
    ACME_L1_SAMPLE,  # §9.2 own org
    ACME_L2_SAMPLE,  # §9.2 own org, other lab
    RIVAL_SAMPLE,  # §9.2 cross-org
    TRAP_SAMPLE,  # segment-boundary trap (org 11 vs org 1)
    WWDB_SAMPLE,  # §9.4
]

# The lineage rows those scopes are derived from: (org, lab, project, sample).
# Order matches FIXTURE_SCOPES; test_fixture_rows_match_scopes asserts the
# correspondence rather than trusting this comment.
FIXTURE_ROWS = [
    (1, 1, 2, 3),
    (1, 2, 9, 7),
    (2, 3, 4, 11),
    (11, 4, 5, 12),
    (9, 5, 6, 13),
]

SCOPE_EXPR = scope_sql(samples="s", labs="l")
