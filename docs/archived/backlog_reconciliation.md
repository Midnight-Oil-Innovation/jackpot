# Backlog Reconciliation — Chat-shorthand-to-real-backlog map (archived)

> **Status: Audit trail preserved 2026-05-16.** This file is a historical reconciliation artifact, not pending work. The chat-shorthand items it describes (`WW-*`, `EPY-*`, `ML-*`, `FML-*`, `DEMO-*`, `TEST-*`, `DOC-*`) were never committed to the real backlog. The doc explains why, and what the real backlog uses instead.
>
> **What this file is.** A 2026-05-11 reconciliation map produced after four rounds of in-chat merges introduced item prefixes (`WW-*` etc.) that didn't exist in the real `todo.md`. The chat had been treating those shorthand IDs as if they were tracked items; this doc audits the actual state and maps every chat shorthand to its real-backlog destination (or marks it as "Net-new" if no real-backlog item exists).
>
> **Headline framings preserved here:**
>
> - Framing 1 — design-thinking that informs future work (most defensible)
> - Framing 2 — candidate items for the real backlog (if/when they get design docs)
> - Framing 3 — re-prioritize existing tracked items (mostly true for wastewater, partially true for federation, not applicable to epi modeling)
>
> **What superseded it.** The real backlog (`docs/todo.md`) is the source of truth for what's tracked. The Cluster B merge (May 2026) absorbed `jackpot_immune_platform_plan.md` and `jackpot_immune_collaboration_scaffolding.md` into `docs/immune_platform.md`, so the doc-references in the reconciliation map's right-hand column are now indirect (chat-shorthand → real-backlog item → strategic-doc home in immune_platform.md / detection_landscape.md / etc.).
>
> **Operational note preserved verbatim** (the §"Operational note for future sessions" content): any substantive task that touches item IDs, phase names, or status assertions must start with `project_knowledge_search` against `todo.md` and the session summary before any writing. That single tool call is the prerequisite. The session summary is the most-recent-context source-of-truth; `userMemories` is recency-lagged and `transcripts/` is whatever the chat happened to discuss, which can be days behind reality on a project moving at JACKPOT's pace.
>
> The Critical Rule 61 worktree-verification discipline from session 21 has the same shape: verify state before action. The doc-writing equivalent is verify backlog before authoring against it.
>
> **If you need to**: trace a chat-shorthand back to a real-backlog item, this file is the map. If you need to add a new item, edit `docs/todo.md` directly — this archive is read-only.

---

# Backlog reconciliation

This doc replaces what I previously called "todo merge lineage." The earlier framing assumed our four rounds of in-chat merges had updated the actual `todo.md`. They hadn't. The chat introduced item prefixes (`WW-*`, `EPY-*`, `ML-*`, `FML-*`, `DEMO-*`, `TEST-*`, `DOC-*`) that don't exist in the real backlog. The real backlog uses `B-IMMUNE-*`, `B-WW-*`, `B-CARE-*`, `B-BYOP-*`, `B-EUK-*`, `B-COLLAB-*`, and `FED-A/B/C/D/E` for federation scaffold work, all consolidated from the immune-platform plan, the immune-collaboration scaffolding, the detection-landscape doc, and several others.

This doc is the map.

## Verified current state (from todo.md, spec.md, session summary, 2026-05-11)

- **Phase 24.5 sovereignty-deletion design**: merged (PR #20, Session 21). `docs/architecture/sovereignty-compliant-deletion.md` exists.
- **FED-A federation Track 1 scaffold**: merged 2026-05-08. `backend/backend/federation/` package: `FederationClient` (L1 query federation), `FederationPushJob` (L2 hub push), `FederationAccessGateway` (L3 bidirectional access), `_ais_hooks.py` Protocol seam, `NullAISFederationHooks` no-op default.
- **PRV-A privacy scaffold**: merged this session (PR #39, maintainer-authored). `backend/backend/privacy/` package mirroring FED-A pattern.
- **FIX-1/FIX-2**: both P0 bugs resolved. Audit forwarding in `log_audit` / `create_notification` corrected; `_handle_workflow_complete` signature fixed.
- **E-1 laptop UAT artifacts**: created but not run. `docs/e2e_uat_plan.md` + `tests/e2e/scripts/` + `tests/fixtures/e2e/` exist. The UAT walks the six-role RBAC matrix end-to-end against a fresh install.
- **P0h Slurm executor campaign**: six of ten blocks landed (H-1 through H-6, plus H-10 docs). H-7 (GCP Batch profile) and H-8 (real-cluster smoke) deferred to Phase 25.
- **CORS_ORIGINS**: validator-level resolved via Q-10. Not a deploy blocker.

## Reconciliation map — chat shorthand to real backlog

| Chat shorthand | Real backlog item | Phase | Status |
|---|---|---|---|
| `WW-1..12` (12-item wastewater schema refactor) | Nothing tracked. Existing schema has only `wastewater_lineage_abundance` result type from Freyja. | n/a | Net-new design. Not in backlog. |
| `WW-2a` consumer-code refactor | Nothing tracked. | n/a | Net-new. |
| `WW-13..26` implementation items | Nothing tracked. | n/a | Net-new. |
| Wastewater dashboard | `B-WW-1` Wastewater lineage-abundance dashboard | Future backlog | 1.5 sessions, unblocked |
| Wastewater NWSS adapter | `B-IMMUNE-WW-1` Wastewater signal ingestion adapter | IM-2 | Tracked, Not Scheduled |
| Wet-side advisory doc | `B-WW-ADV-1` `docs/wetside_advisory.md` | Backlog | 1 day |
| `EPY-S1` `scenario_interventions` schema | Nothing tracked. | n/a | Net-new. |
| `EPY-S2` `epidemic_forecasts` schema | Nothing tracked. | n/a | Net-new. |
| `EPY-S3` `rt_estimates` schema | Nothing tracked. | n/a | Net-new. |
| `EPY-1` epydemix calibration pipeline | Nothing tracked. | n/a | Net-new. |
| `EPY-2` epydemix simulation pipeline | Nothing tracked. | n/a | Net-new. |
| `EPY-3` WhiteLabRt Rt estimation pipeline | Nothing tracked. | n/a | Net-new. |
| `EPY-4..22` (parsers, service, API, UI, CLI, tests, docs) | Nothing tracked. | n/a | Net-new. |
| `ML-1` `model_artifacts` schema | `B-IMMUNE-SCHEMA-1` (Schema v6.0 stub: `detectors`, `detector_activations`, `dca_priority_scores`, `memory_cells` tables, behind `IMMUNE_PILLAR_I_ENABLED=false`) | IM-1.A | Tracked, Not Scheduled |
| `ML-2` `model_evaluations` schema | Subsumed under `B-IMMUNE-SCHEMA-1` table set | IM-1.A | Tracked, Not Scheduled |
| `ML-3` `inference_runs` schema | Subsumed under `B-IMMUNE-SCHEMA-1` | IM-1.A | Tracked, Not Scheduled |
| `ML-4` `embeddings` schema | Subsumed under `B-IMMUNE-SCHEMA-1` (memory_cells carries detector signatures) | IM-1.A | Tracked, Not Scheduled |
| `ML-5` embedding pipeline at ingest | Closest: `B-IMMUNE-FEAT-1` k-mer featurizer + featurizer registry pattern | IM-1.A | Tracked, Not Scheduled |
| `ML-6` batch anomaly scan | `B-AMAND-1` (AMAnD per Price & Russell 2023; canonical metagenome anomaly detector) | IM-1.A | Tracked, Not Scheduled |
| `ML-7` lineage growth anomaly | Not directly tracked; closest is `B-AMAND-1` over time series. Standalone lineage-growth detector would be net-new. | n/a | Net-new for MLR variant. |
| `ML-8` AMR fingerprint anomaly | Not directly tracked. | n/a | Net-new. |
| `ML-9` UShER placement outlier scoring | Not in IM track; could fit under IM-1.B alongside `B-TAXTRIAGE-1`. | n/a | Net-new. |
| `ML-10` generic ML training pipeline | `B-AMAND-1` + Nextflow process pattern is the closest analog | IM-1.A | Tracked, Not Scheduled |
| `ML-11` drift monitoring | Not tracked. | n/a | Net-new. |
| `ML-12..19` parsers/API/UI/CLI/docs | Closest: `B-IMMUNE-API-1` (immune_bio router), `B-IMMUNE-UI-1` (Anomaly Triage Streamlit page) | IM-1.A | Tracked, Not Scheduled |
| `FML-1..2` federation summary stats + coordinator | Conceptual fit with `FederationClient` L1 query federation + `secure_aggregate` AIS hook. Implementation TBD. | FED-A merged; downstream TBD | FED-A landed |
| `FML-3` federated lineage growth | Not tracked. | n/a | Net-new. |
| `FML-4` federated AMR fingerprint | Not tracked. | n/a | Net-new. |
| `FML-5` global reference distribution | Closest: `B-IMMUNE-REP-1` AntibodyRepertoire publish/subscribe | IM-4 | Tracked, Not Scheduled |
| `FML-6` federation API endpoints | `FED-B` (PENDING) — federation router | Active sprint candidate | Pending |
| `FML-7` federation analytics dashboard | Not tracked. | n/a | Net-new. |
| `FML-Y2` full FL with Flower + LoRA | Distributed across `B-IMMUNE-HE-1`, `B-IMMUNE-DP-1`, `B-IMMUNE-MEMSYNC-1`, `B-FED-PILLARIII-1` (FedTADBench benchmarking) | IM-4 | Tracked, Not Scheduled |
| `DEMO-1` `fetch_demo_data.py` | Not tracked. Script delivered in chat but not committed. | n/a | Net-new. |
| `DEMO-2..14` (parsers/forecast/federation partition/etc) | Not tracked. | n/a | Net-new. |
| `TEST-1..12` (testing model) | Not tracked. | n/a | Net-new. |
| `DOC-1..18` (researcher intros + SFI outreach) | Not tracked anywhere; this is operational outreach, not code work. | n/a | Personal/operational backlog. |
| `DEC-1..16` architectural decisions | Some align with existing decisions in spec / immune-plan / scaffolding doc. Need individual mapping. | n/a | Mixed. |
| Phase 26 subsection N (9 B-XXX wastewater adoption) | Phase 26 exists in real backlog (Pathoplexus/Loculus 34 items, Tracked Not Scheduled). The 9 wastewater items are net-new additions. | n/a | Net-new. |
| Phase 26 subsection O (4 B-EPY) | Net-new. | n/a | Net-new. |
| OBS-1..4 (Observatory schema items) | Not tracked. | n/a | Net-new. |

## What this means

Three honest framings of the chat work, in increasing claim-strength:

**Framing 1: design-thinking that informs future work.** The most defensible framing. Our chat explored what wastewater-as-first-class-entity could look like, what an EPISTORM integration could look like, what federation analytics could look like. None of it is committed-to. It exists as context for any future design-and-commit decision.

**Framing 2: candidate items for the real backlog.** If wastewater, federation, and epi modeling are the three priorities (per your direction), the chat content is the design starting point for adding net-new items. Specifically: net-new `B-WW-MODULE-*` items for the deeper wastewater module, net-new `B-EPY-*` items for epi modeling integration, net-new `B-FED-ANALYTICS-*` items for federation analytics on top of FED-A/B/C/D/E. Each net-new item set needs its own design doc (similar to `jackpot_immune_platform_plan.md`) before items get IDs.

**Framing 3: re-prioritize existing tracked items.** For wastewater, this is mostly already true — `B-WW-1` exists and is 1.5 sessions, unblocked. For federation, FED-B/C/D/E are pending and form a complete demo if scheduled. For epi modeling, there is no existing track to re-prioritize; it's entirely net-new.

## Translation work needed before the three demos are buildable

| Demo | Translation work | Effort |
|---|---|---|
| Wastewater | None — `B-WW-1` is unblocked. Optionally add `B-WW-MODULE-*` design doc + items if expanding beyond Freyja-only. | 1.5 sessions for ship; +1 session for design doc if expanding |
| Federation | FED-B/C/D/E need to land. Optionally net-new `B-FED-ANALYTICS-*` items for federation analytics dashboard if that's part of the demo. | 4 sessions for FED-B/C/D/E (one per branch); +1 for analytics design |
| Epi modeling | All net-new. Need an `jackpot_epidemic_modeling_design.md` anchor doc analogous to `jackpot_immune_platform_plan.md`, then enumerate `B-EPY-*` items, then sequence. | 1-2 sessions for design doc; then implementation effort TBD |

## What to do with the 9 chat-summary docs

Each of the other 8 docs is being rewritten with:

- Real backlog item IDs replacing the chat shorthand
- Honest annotation of "tracked" vs "net-new design work"
- Phase status (Active sprint candidate / Tracked Not Scheduled / Net-new)
- Cross-references to source-of-truth design docs that actually exist in the repo

The intent is to convert the chat work from a phantom-baseline fork into legitimate design-thinking that informs future tracked work, not pretend it's already in the backlog.

## Operational note for future sessions

The lesson from this thread is structural, not tactical: any substantive task that touches item IDs, phase names, or status assertions must start with `project_knowledge_search` against `todo.md` and the session summary before any writing. That single tool call is the prerequisite. The session summary is the most-recent-context source-of-truth; `userMemories` is recency-lagged and `transcripts/` is whatever the chat happened to discuss, which can be days behind reality on a project moving at JACKPOT's pace.

The Critical Rule 61 worktree-verification discipline from session 21 has the same shape: verify state before action. The doc-writing equivalent is verify backlog before authoring against it.
