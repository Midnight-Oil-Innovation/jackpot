# JACKPOT Architecture Documents

This directory holds long-form design documents that lock in
architectural decisions before they're implemented. Each doc is
authoritative within its scope; implementation phases reference these
docs as their build spec.

## Active design lockdowns

- **`jackpot-init-cli.md`** — design lockdown for `jackpot init`, the
  operator-bootstrap CLI for the 7 install scenarios (A laptop / B
  single-org cloud / C multi-lab agency / D hosted SaaS / E federation
  member / F CI test / T Tribal-sovereignty). Phase P0e design lockdown.
- **`sovereignty-compliant-deletion.md`** — design for sovereignty-
  compliant data deletion (CARE Principle "Authority to Control"
  alignment). Defines the four-state lifecycle
  (`ACTIVE → DELETION_REQUESTED → TOMBSTONED → VACUUMED`), state
  machine, vacuum cadence, derivative-analysis policy, federation
  propagation requirements, auth model, edge cases, schema constraints
  for P0b, and the implementation handoff to P0c. Phase 24.5 design
  lockdown; schema in P0b; behavior in P0c (`B-CARE-3*`).

## Cross-references

The BYOP + eukaryotic design — sister architectural lockdown to
`sovereignty-compliant-deletion.md` — lives at
`docs/jackpot_byop_and_eukaryotic_design.md` for historical reasons.
Future design docs land here under `docs/architecture/`. Both are named
explicitly in `spec.md` §3 as the lockdowns gating P0b's schema
migration.
