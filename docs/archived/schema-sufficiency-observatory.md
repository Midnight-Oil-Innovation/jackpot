> **Status:** Superseded — archived (directory convention). Historical; do not cite as current.

# Schema sufficiency and Observatory use cases

The chat analyzed four ASU Health Observatory-shaped projects against JACKPOT's schema and proposed `OBS-1..4` schema items. The schema-sufficiency analysis stands as a useful exercise; the `OBS-*` items don't exist in `todo.md` and would be net-new if pursued.

## The four use cases analyzed

| Use case | Anchor | Schema fit verdict | Net-new schema needed |
|---|---|---|---|
| H5N1 statewide consortium | Engelthaler at TGen + ADHS + NAU | Sufficient at base for most fields; dairy bulk milk specifics absent | Yes (chat-named `OBS-1`) — net-new |
| Valley fever / Coccidioides surveillance | Sunenshine (CHS) + Galgiani (Valley Fever COE) | Sufficient for clinical; environmental air-filter sampling specifics absent | Yes (chat-named `OBS-2`) — net-new |
| Measles outbreak tracking | Sunenshine (CHS) | Sufficient. Existing `samples` + `pipeline_results` + `sample_associations` cover. | No |
| Tempe wastewater integration | Lant (Decision Theater) + Halden + Lim | Existing schema has `wastewater_lineage_abundance` from Freyja parser; no first-class site/sample/target entity model | Optional — net-new module if pursued; `B-WW-1` works without |

Three of four come back as "sufficient with small additions" or "sufficient as-is." That's the right confirmation that the schema-first design's payoff is real. The fourth (Tempe wastewater) is the one where the chat went deepest on net-new schema; see `wastewater-roadmap.md`.

## Use case 1 — H5N1 statewide consortium

**Context.** Engelthaler at TGen leads de facto AZ statewide H5N1 sequencing. Sample sources span dairy bulk milk, retail milk, sick cattle, wild birds, raptors, and (rare but increasing) humans. Multi-organization with NAU and ADHS.

**Real schema fit.** Existing `samples` table handles sample provenance well: `host`, `host_health_status`, `isolate_source`, `collection_location`, `collection_date`, plus full taxonomy via the `organisms` reference table. Sector taxonomy supports "animal," "vector," "environment" already. Pipeline results land in `pipeline_results` regardless of host. Federated query across orgs is supported via the FED-A scaffold (with FED-B/C/D/E pending).

**Real gap.** Dairy bulk milk has specific metadata not in the existing schema — bulk tank ID, herd size, milk pickup route, processing plant, days-in-milk distribution, somatic cell count, on-farm vs co-op. These could go in `samples.metadata_jsonb` but lose queryability. The chat proposed a `bulk_milk_sampling_details` typed table referenced from `samples` via optional FK (chat-named `OBS-1`). Same pattern works for retail milk (different field set — store, brand, processing date, expiration, supply chain tier).

**Is this in the backlog?** No. The 4 eukaryotic-pathogen schema items in Phase 24.5 (`B-EUK-1` through `B-EUK-3`) add fields for parasitemia, developmental stage, multiplicity of infection, coinfection — relevant for *Plasmodium* and parasitic-eukaryote work but not for influenza H5N1. Adding dairy bulk milk specifics would be net-new under a new `B-OBS-*` or similar prefix.

**Operational impact if added.** JACKPOT can host the Engelthaler/NAU/ADHS H5N1 consortium without further schema changes beyond the bulk-milk additions. Federated query "show me dairy bulk milk H5N1 detections in Maricopa county Q1 2026 by participating org" works end-to-end once FED-B/C/D/E ship.

## Use case 2 — Valley fever / Coccidioides surveillance

**Context.** Sunenshine at CHS and Galgiani at Valley Fever COE (BIO5/UA + ASU) co-lead the Arizona Coccidioides program. Galgiani's work is heavily clinical; Sunenshine bridges clinical + environmental. The Jin/Wei/Kandala/Umesh/Steele/Galgiani/Laubichler 2025 *Lancet Regional Health–Americas* LSTM paper forecasts case counts in Maricopa County from weather + temporal covariates — case-count-only, no strain resolution. The natural JACKPOT extension is strain-resolved forecasting.

**Real schema fit.** Clinical Coccidioides samples (sputum, BAL, serology) work in existing schema. Pipeline results from antifungal-resistance profiling, MLST, whole-genome workflows all land in `pipeline_results`. The challenge is environmental sampling.

**Real gap.** Air filter sampling for environmental Coccidioides (a key surveillance method given Coccidioides is a soil-dwelling dimorphic fungus that becomes airborne via dust) has its own metadata: filter type and pore size, air volume sampled, collection duration, height above ground, weather conditions during sampling (temperature, humidity, wind, dust storm flag), upstream vs downstream of activity site. Chat proposed `air_filter_sampling_details` typed table referenced from `samples` (chat-named `OBS-2`).

**Is this in the backlog?** No. Net-new if pursued. The eukaryotic-pathogen schema items in Phase 24.5 don't cover air-filter environmental sampling — they're focused on parasitic-eukaryote sample types like blood and stool.

**Generalization bonus.** The same `air_filter_sampling_details` pattern generalizes to other air-filter pathogen surveillance (legionella in cooling towers, anthrax in defense-relevant contexts, dust-storm pathogen panels). Built once, reusable.

## Use case 3 — Measles outbreak tracking

**Context.** Sunenshine at CHS handles measles surveillance for AZ. Historically low volume but with periodic outbreaks (2025 saw renewed activity). Sample types are clinical (throat swabs, urine, blood serology). Strain genotyping done at CDC reference labs.

**Real schema fit.** **No schema changes needed.** Existing `samples` schema covers clinical specimens. `pipeline_results` handles measles N gene genotyping output. `sample_associations` covers epi-linked case clusters (the "outbreak" entity).

**Why this matters.** A clean "schema is sufficient as-is" verdict on one of the four use cases is itself meaningful — confirms the schema-first design's payoff. Schema-first means most new projects don't need schema changes.

## Use case 4 — Tempe wastewater integration

**Context.** Lant at Decision Theater is the analytics anchor; Halden's lab at Biodesign Environmental Health Engineering generates the data; Lim's group at Biodesign Microbiomics does the metagenomic side. City of Tempe publishes the underlying wastewater data (substance use panel included). Tempe catchment includes ASU Tempe campus.

**Real schema fit.** The existing `wastewater_lineage_abundance` result type (from the Freyja parser, landed in pipeline result schemas during Phase 14) covers Freyja's lineage-fraction outputs. `B-WW-1` (1.5-session backlog item) builds the Streamlit dashboard on top. That covers a useful slice — "show me SARS-CoV-2 lineage trajectories for Tempe over the last 6 months" — without schema changes.

**Real gap.** If the goal is full first-class wastewater entity modeling (site as long-lived entity, sample-per-site-per-day, per-pathogen results, multi-target panels including non-SARS-CoV-2 pathogens), that's net-new design work. The chat went deep on this design (called it `WW-1..12` schema items + `WW-13..26` implementation + Phase 34). None of it is tracked.

The deeper module is feasible as net-new design but is much larger than `B-WW-1` ship. Detail in `wastewater-roadmap.md`.

## Integration patterns surfaced (useful regardless)

Three integration patterns came out of the analysis and are worth keeping as principles for any future Observatory use case:

1. **`sample_associations` for context-linking.** When one sample needs to reference another (parent-child relationships in outbreak clusters, paired clinical-environmental samples, technical replicates), use `sample_associations` with a typed `association_type` enum. Avoids ad-hoc JSONB and keeps queries normal-form.
2. **Federated query joins via FED-A/B/C/D/E.** When a use case spans multiple labs (H5N1 consortium, multi-state outbreak), use the federation framework. Don't centralize data; query across cells via `FederationClient` L1 query federation.
3. **`pipeline_results` JSONB for unstructured outputs.** When pipeline output is genuinely unstructured or rapidly-evolving, JSONB in `pipeline_results` is the right answer. Append-only immutability means stable fields can later promote to typed columns without breaking history.

## ICTV taxonomy alignment

**Context.** Arvind Varsani is on the ICTV Executive Committee. ICTV publishes the canonical virus taxonomy with annual revisions (Master Species List). JACKPOT's `organisms` table currently uses NCBI taxonomy; for viruses ICTV is the authoritative source (NCBI lags ICTV by 6-18 months).

**Real gap.** Dual-source virus rows in `organisms`: ICTV master species list ID + NCBI tax ID + ICTV revision year. ICTV-version field on relevant pipeline result types so a sample classified under ICTV 2025-Q3 is queryable distinctly from one classified under ICTV 2026-Q1.

**Strategic value.** Schema item deliberately structured to align with Varsani's domain authority. Reaching out to Varsani about JACKPOT's ICTV alignment positions the conversation correctly — JACKPOT is doing the right thing technically and Varsani is the expert. **The schema design becomes the conversation opener** rather than a generic collaboration ask.

**Is this in the backlog?** No. Net-new. Would fit in Phase 24.5 alongside the existing sovereignty + BYOP/eukaryotic lockdowns if pursued — explicit aim of Phase 24.5 is "lock the schema architecture before P0b touches the schema."

## What's net-new if Observatory use cases become real

If H5N1, Valley fever, or full Tempe wastewater module become deployment priorities, here's what needs to be added to the actual backlog:

| Item | Chat name | Effort | Notes |
|---|---|---|---|
| Dairy bulk milk sampling details schema | `OBS-1` | 1 session | Net-new typed table + samples FK |
| Air filter sampling details schema | `OBS-2` | 1 session | Net-new typed table + samples FK |
| `external_data_sources` reference table | `OBS-3` | 1 session | Reference-only, not ingested data |
| ICTV taxonomy alignment refactor | `OBS-4` | 1-2 sessions | `organisms` dual-source + ICTV-version field |

Each would land in Phase 24.5 alongside `B-CARE-3-DESIGN` (sovereignty deletion) and the BYOP/eukaryotic schema items (`B-BYOP-9`, `B-BYOP-9b`, `B-EUK-1/2/3`) — the same gated-by-P0b lockdown pattern. Splitting them into a later migration creates double-migrate operator churn, exactly the failure mode Phase 24.5 exists to prevent.

The pre-condition for committing any of these is whether the specific Observatory use case is a real deployment priority — not theoretical. The schema-sufficiency analysis is useful exercise either way; turning it into schema work is contingent on the program being real.

## Strategic framing

The Observatory analysis is the bridge between abstract platform capability and concrete demonstrable readiness for the STPH institutional home conversation (per `strategic-coalition.md`). STPH needs JACKPOT to be ready to host real Observatory projects — not just describe them. The dual-PII-gate architecture (NCBI SRA Human Scrubber + GCP Cloud DLP) plus the schema-first design plus the federation scaffold plus the immune platform plan together constitute that readiness package, with or without `OBS-*` schema additions.

If a specific use case becomes the demo deliverable, the analysis here is the design starting point for the specific schema work it would need.
