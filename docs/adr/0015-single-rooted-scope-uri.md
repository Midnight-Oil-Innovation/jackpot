> **Status:** Canonical — architectural decision record.

# Scope URIs are one rooted path under `instance://self`

Every scope reference — in a capability grant, in a policy, and for a resource —
serializes as a path beneath a single root:

```
instance://self
instance://self/org/3
instance://self/org/3/lab/7
instance://self/org/3/lab/7/project/12
instance://self/org/3/lab/7/project/12/sample/55
```

Containment stays what `authz/engine.py::_scope_contains` already does: equality,
or a prefix match at a segment boundary. Nothing about the decision function
changes; it simply becomes true that the instance scope contains a lab scope.

## Why this needed deciding

Nobody had picked a serialization. M0's §9 fixtures invented two shapes
(`instance://field-laptop/org-x/lab-y/...` and `org://acme/lab-1/...`), and the
ACCESS-SEED reseed invented two more (`instance://self` for admins, `lab://7`
for memberships). Prefix containment across unrelated roots is impossible by
construction, so `instance://self` did not contain `lab://7` — the
`admin-bypass-vs-scoped-grants` divergence class the M2 preflight recorded as a
cutover blocker (`docs/m2_preflight_report.md` §4). It read as an admin problem;
it was a serialization problem that happened to surface on admin rows first.

## Alternatives rejected

**Ancestry resolution over short refs** (`lab://7` plus a scope tree that knows
lab 7 sits under org 3). `access_model.md` §5's sketch anticipated this with a
`scope_tree` parameter. It buys refs that survive a lab moving between orgs, and
costs `permit()` its purity — every call site would resolve ancestry first, and
`visibility_sql_clause` would need a recursive CTE instead of a `LIKE`. The two
implementations of one logic are exactly what M1 was built to keep from
diverging, and M2 is the irreversible session. Reconsider if labs ever actually
move between orgs; they do not today.

**An admin ALLOW policy over the existing mixed refs.** Does not work: policy
matching runs through the same `_scope_contains` (`authz/policy.py::_matches`),
so an instance-scoped ALLOW policy misses lab-scoped resources for the same
reason grants do. Making it work needs a wildcard capability at a root scope that
contains everything — `is_platform_admin`'s unconditional bypass, re-implemented
as a policy, which is the thing this redesign exists to delete. It also leaves
org scope unrepresentable, and org is the P0c isolation boundary (§3.2).

## Consequences

Admin reach is structural, not a bypass: the Instance Administrator preset's
`instance://self` grants prefix every resource. Deny-wins is unaffected — a
sovereignty DENY policy still beats a root grant, which is the property the
policy alternative would have quietly lost.

Resource scope is computed from the join the sample list query already performs,
not stored in a column:

```sql
FROM samples s JOIN labs l ON l.id = s.lab_id
-- 'instance://self/org/' || l.organization_id || '/lab/' || s.lab_id
--   || '/project/' || s.project_id || '/sample/' || s.id
```

No denormalized `organization_id` on `samples`, no backfill, no trigger, no
drift. `visibility_sql_clause` takes a scope expression rather than hardcoding
`<alias>.scope`. If the list path gets slow, add an expression index — the
prefix `LIKE` is otherwise a sequential scan.

The cost accepted: scope strings are denormalized state inside grant rows.
Reparenting a lab strands its grants until a single
`UPDATE authz_capability_grants SET scope_ref = replace(...)` repairs them.

Serialization is specified in `docs/access_model.md` §3.1.1. Landing it is M2
work: a scope-URI builder, `reseed.py` joining `labs` for `organization_id`, and
the M0/M1 fixtures rewritten to the canonical shape.
