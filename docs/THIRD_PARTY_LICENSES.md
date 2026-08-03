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

Row shape: `| name | license (SPDX) | version-or-scope | notes |`

## Wrapped tools

| name                      | license                 | version-or-scope           | notes                                  |
| ------------------------- | ----------------------- | -------------------------- | -------------------------------------- |
| GOTTCHA2                  | GPL-3.0                 | LANL/poeli fork            | Taxonomic arm; PanGIA successor        |
| deacon                    | MIT                     | rust minimizer             | Ingest default for host depletion      |
| Cleanifier                | (verify)                | host depletion             | Read LICENSE before wiring             |
| hostile                   | MIT                     |  Host depletion            | verified 2026-08-02 from pyproject.toml classifier + Bioconda recipe              |
| HRRT (sra-human-scrubber) | public-domain (NIH)     | ingest                     | NIH work product                       |
| SeqScreen                 | GPL-3.0                 | functional-concern channel | verified 2026-07-22 against https://gitlab.com/treangenlab/seqscreen/-/raw/master/LICENSE                |
| DeePaC                    | MIT                     | functional-concern channel | verified 2026-07-22 against https://gitlab.com/rki_bioinformatics/DeePaC/-/raw/master/LICENSE            |
| PyOD                      | BSD-2-Clause            | anomaly-detection deps     | Already in nf-core/adjacent ecosystems |
| Jellyfish                 | GPL-3.0                 | k-mer counting             | GPL family; AGPL-compatible            |
| PanGIA                    | (verify — do not adopt) | superseded by GOTTCHA2     | Do not rebuild the 2018 database       |
| alibi-detect              | BSL-1.1                 | REJECTED                   | Not OSS; verified 2026-06              |

## Foundation models (weights + inference code)

| name                      | license    | version-or-scope   | notes                                                    |
| ------------------------- | ---------- | ------------------ | -------------------------------------------------------- |
| METAGENE-1                | Apache-2.0 | 7B decoder-only    | verified 2026-07-22 against https://huggingface.co/datasets/choosealicense/licenses/blob/main/markdown/apache-2.0.md |
| DNABERT-S                 | (verify)   | 117M species-aware | Verify against model card LICENSE before adoption        |
| DNABERT-2                 | (verify)   | ICLR 2024          | Route through this gate before adoption                  |
| Nucleotide Transformer v2 | (verify)   | InstaDeep          | Route through this gate before adoption                  |
| Evo 2                     | (verify)   | Brixi 2025         | Route through this gate before adoption                  |
| MetagenBERT / DNABERT-MS  | (verify)   | 2026               | Verify before continued-pretraining work                 |

## Databases and references

| name                           | license     | version-or-scope      | notes                  |
| ------------------------------ | ----------- | --------------------- | ---------------------- |
| SRA (via branchwater/sourmash) | public data | global-novelty signal | Data license, not code |

## Nextflow pipelines (Apache-2.0 CDC set, adopted)

| name               | license    | version-or-scope                         | notes                                 |
| ------------------ | ---------- | ---------------------------------------- | ------------------------------------- |
| seqsender          | Apache-2.0 | CDC — NCBI/GISAID submission             | Adopt P0i                             |
| MIRA-NF            | Apache-2.0 | CDC — flu/SARS/RSV via IRMA              | Adopt P0i                             |
| PHoeNIx            | Apache-2.0 | CDC — AMR/HAI bacteria                   | Adopt P0i                             |
| MycoSNP-NF         | Apache-2.0 | CDC — fungal (C. auris)                  | Adopt P0m                             |
| Aquascope          | Apache-2.0 | CDC — wastewater SARS-CoV-2              | Adopt P0m                             |
| Tostadas           | Apache-2.0 | CDC — NCBI/GISAID via Liftoff/VADR/Bakta | Adopt P0m                             |
| MicrobeTrace       | Apache-2.0 | CDC — browser-based outbreak viz         | Adopt P0m                             |
| MultiQC            | GPL-3.0    | Seqera                                   | Already used transitively via nf-core |
| Wave (self-hosted) | AGPL-3.0   | Seqera — container provisioning          | AGPL-on-AGPL clean; Adopt P0l         |

## Standards and specs (not licensed code)

| name                | license         | version-or-scope      | notes                   |
| ------------------- | --------------- | --------------------- | ----------------------- |
| GA4GH /service-info | Apache-2.0 spec | federation discovery  | Spec, not runtime       |
| DRS URI conventions | Apache-2.0 spec | file addressing       | Spec, not runtime       |
| PHES-ODM            | MIT             | wastewater data model | Data model, not runtime |
| Crypt4GH            | Apache-2.0 spec | encrypted at rest     | Year 2+                 |
| Beacon v2           | Apache-2.0 spec | federation            | Year 2+                 |

---

**Verification pending.** Every row marked `(verify)` needs its LICENSE read before
the tool or model is wired into production. Do not paste a license claim from a
blog; read the repository's own `LICENSE` file, and update the row with the exact
SPDX identifier plus the release you verified against. This is the discipline that
prevented the alibi-detect adoption (documented as BSL-1.1 in its own LICENSE file
despite third-party claims of Apache-2.0).
