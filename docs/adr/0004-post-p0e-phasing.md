> **Status:** Canonical — architectural decision record.

# Phase ordering after the April 2026 pivot

Work sequences as: cleanup phases 6.1–11 → P0d (monorepo migration) → P0e
(install/CLI) → Phase 24.5 (architectural design lockdown) → P0f (BYOP
infrastructure) → P0b (Schema v5.0) → P0c (multi-tenancy middleware and
sovereignty deletion) → P1–P5.

The non-obvious ordering is that the design lockdown (24.5) precedes the
schema migration (P0b) rather than accompanying it. Locking the sovereignty
deletion model and the BYOP/eukaryotic schema shape first means P0b is one
migration instead of three, avoiding repeated operator-deploy churn.

## Status

Largely executed. P0d, P0e, 24.5, and P0b have all landed; P0b's migration is
`c871b28bbdab`, merged 2026-07-06.
