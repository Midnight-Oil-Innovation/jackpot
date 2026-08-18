> **Status:** Superseded — archived (directory convention). Historical; do not cite as current.

# Demo data sources

Public data sources for the laptop Scenario A demo. The "Sol cluster federation simulation" framing from chat doesn't apply — Glen's demo target is laptop deployment, which means two JACKPOT instances on one laptop via Docker Compose for federation; the data sources stay the same.

## What the demo is actually for

The right framing is **lineage-resolved or genotype-resolved forecasting**, which JACKPOT is positioned to do better than non-genomic platforms. Case-count forecasting is solved by the COVID-19 Forecast Hub. JACKPOT's natural demo question: "does a lineage-resolved forecaster beat case-count-only forecasts for the same Arizona period?"

The laptop demo combines:

1. Wastewater visualization via `B-WW-1` (the existing 1.5-session backlog item that builds a Streamlit dashboard on the `wastewater_lineage_abundance` Freyja outputs).
2. Optional anomaly-detection slice via the IM-1 demo path (`B-IMMUNE-SCHEMA-1` + `B-AMAND-1` against synthetic data corpus from `B-SYNTH-DATA-1`).
3. Optional federation slice via two laptop instances post-FED-B/C/D/E.

None of this requires GCP staging.

## Sequence data sources

**NCBI Virus and NCBI GenBank.** Hundreds of thousands of SARS-CoV-2 sequences, fully public, no access-control terms. Available via NCBI Datasets API or Virus portal. Right starting point — genuinely open, JACKPOT can publish demos based on it without legal complications.

**NCBI SRA.** Raw sequencing reads from SARS-CoV-2 studies. Useful for full ingest-to-results pipeline demos.

**COG-UK** consortium data. ~2M sequences from the UK, fully public.

**Pathoplexus / Loculus.** Newer fully-open initiative; smaller dataset than NCBI. Useful comparison point given Phase 26 (Pathoplexus/Loculus comparative analysis, Tracked Not Scheduled) is in JACKPOT's backlog.

**GISAID EpiCoV.** 16M+ sequences but access-controlled. Access terms mean you can't redistribute or publish derived datasets without each user agreeing to the EpiCoV terms. Not ideal for an open demo.

## Lineage and clade assignment

**Pangolin / PangoLEARN** for Pango lineage assignment from sequences. Open source. JACKPOT already runs viralrecon (per spec.md) which includes pangolin and nextclade.

**Nextclade** for clade assignment plus QC. Open source.

**CoV-Spectrum / GenSpectrum LAPIS API** for queryable lineage frequencies over time, by location. Free, no auth for basic queries. The closest existing API to what JACKPOT eventually exposes itself. Reference for the LAPIS-compat work that's part of `B-INSAFLU-1` adoption.

**outbreak.info** from Scripps — similar queryable interface, also free.

## Case / hospitalization context

| Source | Coverage | Status |
|---|---|---|
| CDC COVID Data Tracker | Historical | Agency stopped active updates 2023; CSVs remain |
| HHS COVID-19 Reported Patient Impact | Jan 2020 – Apr 2024 | Frozen but downloadable |
| Our World in Data | Curated time-series, ongoing | MIT-licensed |
| Johns Hopkins CSSE | US county-level until 3/2023 | Comprehensive historical archive |
| NHSN HRD (Hospital Respiratory Data) | Nov 2024 onward | Replaced legacy COVID reporting after CMS reinstated requirement |

The historical-to-current methodology change at the May 2024 / November 2024 seam is real. Voluntary reporting May–October 2024 is incomplete. For continuous time series you stitch and document the methodology change at the seam.

## Wastewater data

**CDC NWSS** — public dashboard data, queryable Socrata API. Two Socrata datasets:

- SARS-CoV-2 wastewater metric data: `data.cdc.gov/resource/2ew6-ywp6`
- SARS-CoV-2 wastewater concentration data (raw): `data.cdc.gov/resource/g653-rqe2`

`wwtp_jurisdiction` is reporting state. Site-level granularity preserved via `key_plot_id` and sewershed-level identifier. Treatment plant names anonymized — you get "AZ_NWSS_FAC_03" with population served, county, approximate location bracket. `county_names` field contains "Maricopa" for sites whose sewershed overlaps the county.

**WastewaterSCAN** — Stanford-led, ASU is a participating site (Halden, Lim). Public dashboard with sample-level data.

**City of Tempe Open Data** — the unsung hero for ASU-anchored demos. Tempe's wastewater catchment includes the ASU Tempe campus. Tracks a broader pathogen panel than NWSS — SARS-CoV-2, flu A/B, RSV, mpox, norovirus, plus drugs of abuse. Available via Tempe's ArcGIS Hub at `data.tempe.gov`. If you do nothing else for an ASU-anchored demo, building on Tempe's data is the highest-value move because (a) unusually granular for a public source, (b) covers ASU campus catchment specifically, (c) includes panels NWSS doesn't publish, (d) built-in audience (City of Tempe and ASU facilities team).

The chat's `DEMO-11` (City of Tempe wastewater feed integration) was a phantom item — not in todo.md. If Tempe data ingest becomes a real priority, it would be a net-new backlog item that depends on `B-WW-1` ship or extends `B-IMMUNE-WW-1`.

## Benchmark — COVID-19 Forecast Hub

The Reich Lab COVID-19 Forecast Hub at UMass Amherst. Gold standard. Collected weekly forecasts from dozens of teams over the entire pandemic, with ground truth. Standardized quantile distributions. Hub publishes evaluation metrics.

GitHub: `reichlab/covid19-forecast-hub` (archived, current through ~2022); `cdcepi/Flusight-forecast-hub` (active successor, generalized beyond flu).

Comparison metric is weighted interval score (WIS) per Bracher et al. 2021. JACKPOT forecast outputs would need to conform to the standardized format for direct comparison — that's net-new design work, not currently tracked.

## CDC data reliability caveat

CDC data infrastructure has been turbulent. The Jan 6, 2025 archival meant some pages disappeared; `restoredcdc.org` exists as a mirror. The Socrata datasets above were live when checked, but run fetch on day one of any project, cache locally, don't depend on continuous availability for production. For a research demo this is fine.

NHSN HRD facility-level data isn't easily accessible without credentials. Public access is state-jurisdiction level only. Facility-level requires SAMS (Secure Access Management Services). This is one of the legitimate gaps JACKPOT-as-platform fills: a real JACKPOT deployment with RBAC + audit story enables SAMS-credentialed users to access facility data within permissioned tiers.

## Recommended laptop demo dataset

For a focused ASU-resonant laptop demo:

1. NCBI Virus sequences with `country:USA` and `state:Arizona` for 2021-01 through 2023-06. Tens of thousands of sequences.
2. Pango lineage assignments via Pangolin or Nextclade (pre-computed or via JACKPOT's existing viralrecon pipeline).
3. Maricopa County wastewater data from NWSS (metric + concentration).
4. Arizona hospitalization data from HHS (historical) + NHSN HRD (current).
5. Held-out future period 2023-07 through 2023-12 for forecast evaluation if doing the forecasting demo.
6. Comparison forecasts from COVID-19 Forecast Hub for same period and location.
7. City of Tempe wastewater feeds for ASU-campus-specific signal.

For federation demo: partition the same dataset by simulated cell-of-origin across two laptop instances. Geographic partition (e.g. Maricopa County to one cell, rest of Arizona to the other) is the simplest meaningful split.

## Fetch script — not tracked

The `fetch_demo_data.py` script delivered in chat (sodapy Socrata client, pulls NWSS metric + concentration, HHS legacy, NHSN HRD current, NCBI Virus metadata) is not committed anywhere. It exists as text in the chat transcript. If demos move forward, committing it to a `tests/fixtures/demo/` or `scripts/` location is a quick-win — same shape as the `tests/e2e/scripts/` helper-script set landed by E-1 in Session 21.

Sequence FASTA fetch is a separate NCBI Datasets CLI command, not Socrata. Pattern: `datasets download virus genome taxon SARS-CoV-2 --geo-location 'USA:Arizona'`.

## What from the chat content isn't tracked

The chat enumerated `DEMO-1..14` items spanning fetch script integration, Pangolin/Nextclade preprocessing, NWSS adapter, HHS context ingest, forecaster baseline, federation partitioning utility, Sol cluster runbook, federation gain measurement harness, Forecast Hub comparison adapter, LAPIS comparison adapter, Tempe integration, demo notebook gallery, reproducibility manifest, end-to-end docs.

None of those item IDs exist in todo.md. The closest tracked work is the E-1 UAT (created Session 21, not yet run) at `docs/e2e_uat_plan.md` + `tests/e2e/scripts/`. That's a six-role RBAC walkthrough using synthetic CSV/XLSX fixtures plus optional real SARS-CoV-2 Arizona-shaped fixtures. It's not a forecasting demo; it's a "does the platform work end-to-end" demo.

If a forecasting demo becomes a real priority, that's net-new design work — analogous to how the immune platform got `jackpot_immune_platform_plan.md` as an anchor design doc before its `B-IMMUNE-*` backlog items got committed.

## Demo path summary

**Today (no new work):** Run the E-1 UAT against current `development`. Validates the platform end-to-end on a laptop with six-role RBAC, two-tier (smoke + full) test plan, real or synthetic SARS-CoV-2 fixtures. Demonstrates the platform works; doesn't demonstrate forecasting or federation specifically.

**Plus `B-WW-1` (1.5 sessions):** Add the wastewater lineage-abundance Streamlit dashboard on top of existing Freyja outputs. Visualizable Tempe / Maricopa wastewater story.

**Plus FED-B/C/D/E (~4 sessions):** Two laptop instances do query federation, hub push, bidirectional access. Federation architecture demo.

**Plus `B-IMMUNE-SCHEMA-1` + `B-AMAND-1` + supporting items (~2-3 weeks):** Bio-AIS anomaly detection vertical slice. Synthetic data corpus generated by `B-SYNTH-DATA-1`.

That stack of work — none of it requires GCP, all of it runs on a laptop — covers the three priorities you named (wastewater, epi modeling, federation) at demoable resolution. The epi-modeling piece is the gap; nothing tracked. Net-new design work needed there (see `epistorm-integration.md`).
