> **Status:** Canonical — architectural decision record.

# BYOP accepts four pipeline source types

A pipeline may be registered from a public Git URL (pinned to tag, branch, or
SHA), private Git with per-pipeline deploy keys held in the operator's secret
manager, an uploaded tar.gz capped at 500 MB compressed, or a Docker image
with a manifest path.

Per-pipeline deploy keys rather than one shared key means revoking access to a
single private pipeline never breaks the others. Constraints per source type
are documented in §4 of `docs/byop_and_eukaryotic_design.md`.
