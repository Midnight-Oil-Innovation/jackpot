# Third-party licenses (JACKPOT wrapped tools and models)

> **Status:** Canonical — source of truth for wrapped-tool and model licenses. Registered in domain_reference.md.
> **Gated by:** `scripts/verify_licenses.py` (B-LICENSE-1).

Every OSS tool, model, or database JACKPOT invokes as a subprocess, container, or
model artifact appears in the table below. Python library dependencies are covered
by pip metadata and do not need entries here; add a row only if a package's declared
license is missing or the gate incorrectly rejects a compatible one.

**Rules of use:**

1. AGPL-3.0 outbound means AGPL, GPL, LGPL, Apache-2.0, MIT, BSD, ISC, MPL-2.0,
   PSF, Zlib, and public-domain inbound are compatible. GPL is compatible via §13.
2. Business Source, Commons Clause, Elastic 2.x, SSPL, research-only, and
   non-commercial licenses are hard rejections regardless of technical merit.
3. Undeclared or ambiguous licenses default to rejected. Read the tool's own
   `LICENSE` file (not a blog, not the readme summary) before adding a row.
4. When a row here disagrees with pip's metadata, this file wins; use the `notes`
   column to explain the discrepancy.

**Adoption scoping (what the gate actually enforces).** This file is both the
dependency inventory and the record of what was evaluated and turned down. Only
the first is a license gate: flagging a tool we rejected *because* its license is
incompatible would make the check cry wolf. A row is informational, and therefore
recorded but never gated, when it carries a `[rejected]`, `[candidate]`, or
`[informational]` marker, when its text says REJECTED / do not adopt / not
adopted / not in use / evaluated only, or when it sits under a section heading
scoping the whole table that way. Everything else is a real dependency and must
clear the gate. Run `verify_licenses.py --report` to see the split, or
`--strict` to audit every row including the informational ones.

Row shape: `| name | license (SPDX) | version-or-scope | notes |`

## Wrapped tools

| name | license | version-or-scope | notes |
|------|---------|------------------|-------|
| GOTTCHA2 | GPL-3.0 | LANL/poeli fork | Taxonomic arm; PanGIA successor |
| deacon | MIT | rust minimizer | Ingest default for host depletion |
| Cleanifier | (verify) | host depletion | Read LICENSE before wiring |
| hostile | MIT | 2.0.2 | Host depletion; verified 2026-08-02 from pyproject.toml classifier + Bioconda recipe. Deletes rather than N-masks; `--rename` strips read-header PII |
| HRRT (sra-human-scrubber) | public-domain (NIH) | ingest | NIH work product |
| SeqScreen | GPL-3.0 | functional-concern channel | Confirm current release |
| DeePaC | (verify) | functional-concern channel | Read LICENSE before wiring |
| PyOD | BSD-2-Clause | anomaly-detection deps | Already in nf-core/adjacent ecosystems |
| Jellyfish | GPL-3.0 | k-mer counting | GPL family; AGPL-compatible |
| PanGIA | (verify — do not adopt) | superseded by GOTTCHA2 | Do not rebuild the 2018 database |
| alibi-detect | BSL-1.1 | REJECTED | Not OSS; verified 2026-06 |

## Foundation models (weights + inference code)

| name | license | version-or-scope | notes |
|------|---------|------------------|-------|
| METAGENE-1 | Apache-2.0 | 7B decoder-only | Edge/cloud tiers; wastewater-pretrained; clears the gate |
| DNABERT-S | (verify) | 117M species-aware | Verify against model card LICENSE before adoption |
| DNABERT-2 | (verify) | ICLR 2024 | [candidate] Route through this gate before adoption |
| Nucleotide Transformer v2 | (verify) | InstaDeep | [candidate] Route through this gate before adoption |
| Evo 2 | (verify) | Brixi 2025 | [candidate] Cloud tier; verify weights license separately from code license |
| MetagenBERT / DNABERT-MS | (verify) | 2026 | [candidate] Verify before continued-pretraining work |

## Databases and references (not licensed code)

Data sources JACKPOT queries, not code it incorporates. AGPL-3.0 copyleft
governs distributed code, so these rows are recorded rather than gated — the
`(not licensed code)` in the heading is what exempts them, matching
`## Standards and specs (not licensed code)` below.

**This section is silent on data-use terms**, which are a separate compliance
question from licence compatibility: redistribution rights, attribution
requirements, and whether derived results may be published. That is fine while
the only entry is public-domain US government data. It stops being fine the
first time a restricted source lands here — GISAID being the obvious one for
this domain. Tracked as `B-LICENSE-DATA-TERMS`.

| name | license | version-or-scope | notes |
|------|---------|------------------|-------|
| SRA (via branchwater/sourmash) | public data | global-novelty signal | US public domain; queried, never redistributed |

## Python dependency overrides

Only for packages whose own installed metadata declares no usable license, so the
gate cannot read one. Verify against the `LICENSE` file in the installed
distribution before adding a row here.

| name | license | version-or-scope | notes |
|------|---------|------------------|-------|
| google-crc32c | Apache-2.0 | transitive via google-cloud-storage | Ships no License-Expression, License field, or trove classifier; verified 2026-08-04 from `LICENSE` in the installed dist-info (googleapis/python-crc32c) |

## Nextflow pipelines (Apache-2.0 CDC set, adopted)

| name | license | version-or-scope | notes |
|------|---------|------------------|-------|
| seqsender | Apache-2.0 | CDC — NCBI/GISAID submission | Adopt P0i |
| MIRA-NF | Apache-2.0 | CDC — flu/SARS/RSV via IRMA | Adopt P0i |
| PHoeNIx | Apache-2.0 | CDC — AMR/HAI bacteria | Adopt P0i |
| MycoSNP-NF | Apache-2.0 | CDC — fungal (C. auris) | Adopt P0m |
| Aquascope | Apache-2.0 | CDC — wastewater SARS-CoV-2 | Adopt P0m |
| Tostadas | Apache-2.0 | CDC — NCBI/GISAID via Liftoff/VADR/Bakta | Adopt P0m |
| MicrobeTrace | Apache-2.0 | CDC — browser-based outbreak viz | Adopt P0m |
| MultiQC | GPL-3.0 | Seqera | Already used transitively via nf-core |
| Wave (self-hosted) | AGPL-3.0 | Seqera — container provisioning | AGPL-on-AGPL clean; Adopt P0l |

## Standards and specs (not licensed code)

| name | license | version-or-scope | notes |
|------|---------|------------------|-------|
| GA4GH /service-info | Apache-2.0 spec | federation discovery | Spec, not runtime |
| DRS URI conventions | Apache-2.0 spec | file addressing | Spec, not runtime |
| PHES-ODM | MIT | wastewater data model | Data model, not runtime |
| Crypt4GH | Apache-2.0 spec | encrypted at rest | Year 2+ |
| Beacon v2 | Apache-2.0 spec | federation | Year 2+ |

---

**Verification pending.** Every row marked `(verify)` needs its LICENSE read before
the tool or model is wired into production. Do not paste a license claim from a
blog; read the repository's own `LICENSE` file, and update the row with the exact
SPDX identifier plus the release you verified against. This is the discipline that
prevented the alibi-detect adoption (documented as BSL-1.1 in its own LICENSE file
despite third-party claims of Apache-2.0).
