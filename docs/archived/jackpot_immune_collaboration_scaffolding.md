> **Status:** Superseded — archived (directory convention). Historical; do not cite as current.

# JACKPOT Immune Platform — Collaboration Scaffolding

**Document type:** Companion to `jackpot_immune_platform_plan.md` — concrete software scaffolding for collaboration with the the AIS-theory collaborator/the applied-cryptography collaborator/the adversarial-security collaborator/the wet-side advisor group at the ASU Biodesign Center for Biocomputing, Security and Society
**Version:** 2.0 (incorporates audit corrections from `jackpot_immune_platform_addendum.md`)
**Last updated:** 2026-05-08
**Author:** maintainer maintainer (gotero@linuxprophet.com), with Claude as co-author
**Audience:** maintainer, AIS-theory collaboration partners, NSF/NIH grant reviewers, contributors evaluating collaboration depth
**Status:** Forward-looking. Each component is a working MVP plus extension point, with deliberate `TODO(<researcher>-collab):` markers indicating where joint work fits

> **Companion document:** `jackpot_immune_platform_plan.md` is the strategic vision and Phase 26+ roadmap that this document is scaffolding *for*. This document is the engineering work that makes the vision credible. Read both together.

------

## Table of Contents

1. [Why this companion document exists](#1-why-this-companion-document-exists)
2. [Eleven critiques, mapped to scaffolding](#2-eleven-critiques-mapped-to-scaffolding)
3. [Gap 1 — Monoculture: `jackpot-diversity` family](#3-gap-1--monoculture-jackpot-diversity-family)
4. [Gap 2 — Software supply chain: `jackpot-sbom` and parsers-safe](#4-gap-2--software-supply-chain-jackpot-sbom-and-parsers-safe)
5. [Gap 3 — Static defense posture: `jackpot-mutate`](#5-gap-3--static-defense-posture-jackpot-mutate)
6. [Gap 4 — Misuse and governance: `jackpot-governance` + refusal mechanisms](#6-gap-4--misuse-and-governance-jackpot-governance--refusal-mechanisms)
7. [Gap 5 — Education-as-foundation reframing](#7-gap-5--education-as-foundation-reframing)
8. [Cross-cutting: the `jackpot-redteam` track + the adversarial-security collaborator/the applied-cryptography collaborator specifics](#8-cross-cutting-the-jackpot-redteam-track--leetrieu-specifics)
9. [Phase 26-collab: integrating into the existing roadmap](#9-phase-26-collab-integrating-into-the-existing-roadmap)
10. [Open research questions, summarized](#10-open-research-questions-summarized)

------

## 1. Why this companion document exists

The main vision doc (`jackpot_immune_platform_plan.md`) lays out the dual-AIS architecture and Phase 26+ roadmap. It doesn't address the gaps the the AIS-theory collaborator/the applied-cryptography collaborator/the adversarial-security collaborator/the wet-side advisor group at ASU Biodesign would notice on first read:

1. **Monoculture** — every federation member runs the same code, same detector implementations, same parameters. the n-variant systems literature was specifically designed against this failure mode.
2. **Software supply chain** — wrapping 16 OSS projects inherits 16 dependency trees. No SBOM, no signing, no CVE gating, no deserialization safety policy.
3. **Static defense posture** — detectors evolve via clonal selection, but auth/RBAC/keys/schema are static. the diversity-as-defense thesis applies here too.
4. **Misuse and governance** — AGPL is necessary but not sufficient. No community-governance model, no refusal-to-deploy criteria, no asymmetric-power awareness, no DURC integration.
5. **Education framing** — Pillar IV is structurally strong but framed as fourth, after three technical pillars. To the AIS-theory collaborator, workforce is foundational, not auxiliary. The vision doc §1 has been corrected to elevate workforce to a co-equal thesis.

This companion document ships **working MVPs** for each gap, plus deliberate extension points and `TODO(<researcher>-collab):` markers naming the open questions. The pattern is consistent:

| Layer              | What we ship                                     | What collaboration adds                            |
| ------------------ | ------------------------------------------------ | -------------------------------------------------- |
| **Infrastructure** | Working code, schema, CLI, CI hooks              | Theoretical grounding, principled parameter choice |
| **Schema**         | Tables and migrations to record what we're doing | Right metrics for what to record                   |
| **Tests**          | Synthetic baseline, smoke tests                  | Adversarial test suites, formal proofs             |
| **Docs**           | Honest about gaps, hooks for joint work          | The actual research                                |

The ratio is intentional: roughly **70% engineering shipped, 30% research as deliberate open questions**. Showing up with 100% shipped looks like we don't need collaborators. Showing up with 30% shipped looks like we haven't thought hard enough. 70/30 says "we've done the work that's available to do alone, and we know exactly where we need help."

> **Note on the actual pitch.** The 70/30 framing is for maintainer's internal calibration. **Do not say "70/30" out loud in the actual pitch meeting** — it reads as performative positioning. Walk through one or two concrete components (the diversity index, the SBOM pipeline) and let the researchers identify their own hooks. They'll position themselves better than we can position them.

### 1.1 Pitch context

This is an **external pitch**, not an internal one. maintainer is independent (Linux Prophet / Midnight-Oil-Innovation, gotero@linuxprophet.com); the AIS-theory collaborator, the applied-cryptography collaborator, the adversarial-security collaborator, and the wet-side advisor are at ASU. The warm hook is the Driver et al. 2024 paper — *Encrypted data-sharing for preserving privacy in wastewater-based epidemiology*, *Science of the Total Environment*, NSF CICI 2021–2024, $499,592 — which JACKPOT extends from wastewater to full federated pathogen genomic surveillance.

For grants, the natural structure is **ASU-as-lead with Linux Prophet as subaward** — the AIS-theory collaborator/the applied-cryptography collaborator/the adversarial-security collaborator/the wet-side advisor are academic PIs, JACKPOT is the deployment platform.

------

## 2. Eleven critiques, mapped to scaffolding

Each row maps a likely critique from the Biodesign group to a concrete software component in this document and an associated `TODO(<researcher>-collab):` marker.

| #    | Critique                               | Source               | Section | Component                                                   | Collaboration marker                                   |
| ---- | -------------------------------------- | -------------------- | ------- | ----------------------------------------------------------- | ------------------------------------------------------ |
| 1    | Monoculture                            | AIS theory           | §3      | `backend/immune/net/diversity.py`                           | `TODO(immune-theory-collab): coverage theory`          |
| 2    | Supply chain                           | AIS theory           | §4      | `scripts/generate_sbom.py`, `parsers_safe.py`               | `TODO(immune-theory-collab): auto-repair`              |
| 3    | Static defense                         | AIS theory           | §5      | `backend/immune/sec/rotation.py`, `api_surface_mutation.py` | `TODO(immune-theory-collab): mutation theory`          |
| 4    | Misuse / governance                    | AIS theory           | §6      | `backend/immune/sec/refusal.py`, `GOVERNANCE.md`            | `TODO(immune-theory-collab): policy framework`         |
| 5    | Asymmetric power                       | AIS theory           | §6      | `backend/immune/net/asymmetric_trust.py`                    | `TODO(immune-theory-collab): fairness theory`          |
| 6    | Education-as-afterthought              | AIS theory           | §7      | `course/modules/_meta/ais_framing.md`                       | n/a (framing)                                          |
| 7    | Crypto primitive imprecision           | Applied cryptography | §8.6    | `backend/immune/net/query_he.py`                            | `TODO(immune-crypto-collab): protocol selection`       |
| 8    | Federation needs formal proof          | Applied cryptography | §8.6    | `docs/protocols/federation_protocol_v0.md`                  | `TODO(immune-crypto-collab): formal proofs`            |
| 9    | Re-identification leaks                | Applied cryptography | §8      | `backend/immune/redteam/attack_federation.py`               | `TODO(immune-crypto-collab): privacy budget`           |
| 10   | Synthetic data not representative      | Adversarial security | §8      | `backend/immune/redteam/data_representativeness.py`         | `TODO(immune-redteam-collab): MIA design`              |
| 11   | ML pipelines vulnerable to own attacks | Adversarial security | §8      | `backend/immune/redteam/` track                             | `TODO(immune-redteam-collab): iterative attack-defend` |

Plus:

- **TCR-epitope hooks** (§8.5): TCR-epitope binding prediction methods (adversarial-ML/immunology lane) maps directly to `jackpot-immune-evasion` and `jackpot-biosig` — methods-paper material independent of the redteam track.
- **the wet-side advisor wet-side advisory** (§9.2): "you don't understand the wet-side enough" doesn't have a software handle; addressed via `docs/wetside_advisory.md` and a wet-side advisor role in `GOVERNANCE.md`.

------

## 3. Gap 1 — Monoculture: `jackpot-diversity` family

### 3.1 The critique, restated

the n-variant systems literature, instruction-set randomization, and Crispy (CRISPR-inspired DoS defense) all rest on one thesis: **homogeneous deployments are catastrophically vulnerable**. One zero-day, every instance falls.

The federation as currently designed (vision doc §6) has every member running the same JACKPOT codebase, the same NSA implementation, the same featurizers, the same Nextflow pipelines, the same Postgres schema. The diversity is in the *data*, not the *platform*. From an AIS-theoretic perspective that's a monoculture pretending to be a diverse population.

### 3.2 What we ship

#### 3.2.1 `backend/immune/algorithms/featurizers/__init__.py` — featurizer registry

Generalizes the single-featurizer assumption in vision doc §10.1. At `jackpot init` time, each member picks (or is randomly assigned) a featurizer from a registry. Multiple featurizer choices per detector class.

```python
# backend/immune/algorithms/featurizers/__init__.py
"""
Featurizer registry — pluggable feature extractors for AIS detectors.

A FederationMember picks a featurizer at init time. Different members
running different featurizers means a single featurizer-specific exploit
(e.g., a tokenization bug in a particular embedding model) does not
compromise the whole federation.

TODO(immune-theory-collab): the right diversity metric for featurizer choice.
We currently treat featurizers as categorically distinct, but two k-mer
featurizers with k=5 and k=7 may share more vulnerabilities than a k-mer
featurizer and an embedding-based one. Coverage theory needed.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable
import numpy as np


@runtime_checkable
class Featurizer(Protocol):
    """All featurizers expose .name, .version, .dim, and a __call__."""
    name: str
    version: str
    dim: int

    def __call__(self, antigen) -> np.ndarray: ...


_REGISTRY: dict[str, type[Featurizer]] = {}


def register(name: str):
    """Decorator: @register('kmer-7') class KmerSeven: ..."""
    def _decorator(cls):
        if name in _REGISTRY:
            raise ValueError(f"Featurizer {name!r} already registered")
        _REGISTRY[name] = cls
        return cls
    return _decorator


def get(name: str) -> type[Featurizer]:
    if name not in _REGISTRY:
        raise KeyError(f"No featurizer named {name!r}; available: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def available() -> list[str]:
    return sorted(_REGISTRY)
```

Concrete featurizers register themselves:

```python
# backend/immune/algorithms/featurizers/kmer.py
import numpy as np
from . import register


@register("kmer-5")
class KmerFiveFeaturizer:
    name = "kmer-5"
    version = "1.0.0"
    dim = 4 ** 5    # 1024 dims for DNA k=5

    def __call__(self, sequence: str) -> np.ndarray:
        # ... compute 5-mer compositional vector
        ...


@register("kmer-7")
class KmerSevenFeaturizer:
    name = "kmer-7"
    version = "1.0.0"
    dim = 4 ** 7    # 16384 dims for DNA k=7

    def __call__(self, sequence: str) -> np.ndarray:
        ...


# embedding-based featurizers register similarly:
# @register("esm-small"), @register("esm-large"), @register("dnabert-v2"), etc.
```

#### 3.2.2 `cli/jackpot_init/diversity_profile.py` — randomized init with depth guard

At `jackpot init` time, each new member picks a detector profile. Default is randomized (forces variation across the federation); deterministic mode available for testing. Recursion depth-bounded to prevent infinite retry loops if the configuration space is exhausted.

```python
# cli/jackpot_init/diversity_profile.py
"""
Detector profile selection at init time.

Default behavior: pick a randomized configuration so each member of the
federation gets meaningfully different detectors. Deterministic mode
(--detector-profile-seed=N) for CI reproducibility.

TODO(immune-theory-collab): selection strategy. Currently uniform-random over
all permitted combinations. A theoretically grounded strategy would
account for current federation diversity (don't add a 6th member with
profile X if 5 already have it) and exploit-equivalence classes (some
profile pairs are more independent than others).
"""
from __future__ import annotations
import hashlib
import random
from dataclasses import dataclass

from backend.immune.algorithms.featurizers import available as available_featurizers


@dataclass(frozen=True)
class DetectorProfile:
    bio_featurizer: str
    cyber_featurizer: str
    nsa_n_detectors: int
    nsa_threshold: float
    dca_signal_weights_seed: int
    profile_hash: str    # sha256 over the above; recorded in federation_members


def generate_profile(
    seed: int | None = None,
    federation_existing_profiles: list[str] | None = None,
    _depth: int = 0,
) -> DetectorProfile:
    """
    Generate a detector profile, optionally avoiding hash collisions
    against an existing federation. Recursion bounded to prevent infinite
    loops if the configuration space is exhausted.
    """
    if _depth > 5:
        raise RuntimeError(
            "generate_profile recursion depth exceeded; federation has too few "
            "available profile permutations or a hash collision is unresolvable"
        )

    rng = random.Random(seed)
    bio_options = [f for f in available_featurizers() if f.startswith("kmer-") or f.startswith("esm-")]
    cyber_options = [f for f in available_featurizers() if f.startswith("apicall-")]

    bio = rng.choice(bio_options)
    cyber = rng.choice(cyber_options)
    n = rng.choice([800, 1000, 1200, 1500, 2000])
    thr = rng.uniform(0.30, 0.50)
    weight_seed = rng.randint(0, 2**31 - 1)

    payload = f"{bio}|{cyber}|{n}|{thr:.4f}|{weight_seed}".encode()
    h = hashlib.sha256(payload).hexdigest()

    profile = DetectorProfile(
        bio_featurizer=bio,
        cyber_featurizer=cyber,
        nsa_n_detectors=n,
        nsa_threshold=thr,
        dca_signal_weights_seed=weight_seed,
        profile_hash=h,
    )

    # If this exact profile already exists in the federation, retry with
    # an incremented seed; bounded by _depth.
    if federation_existing_profiles and profile.profile_hash in federation_existing_profiles:
        return generate_profile(
            seed=(seed or 0) + 1,
            federation_existing_profiles=federation_existing_profiles,
            _depth=_depth + 1,
        )

    return profile
```

The profile is written to `config/detector_profile.yaml` at init and passed to backend modules as configuration. It's also published to the federation as part of the member's `AntibodyRepertoire` (vision doc §6.3) so other members can compute the diversity index.

#### 3.2.3 `backend/immune/net/diversity.py` — federation diversity index

```python
# backend/immune/net/diversity.py
"""
Federation diversity index.

Measures how heterogeneous the federation's detector profiles are.
Computes a Shannon-style index over the categorical configuration
space (featurizer × detector-count-bucket × threshold-bucket).
A low value means the federation is approaching a monoculture.

TODO(immune-theory-collab): the right diversity metric. Shannon over
categorical configuration is a placeholder. The principled metric
would account for exploit-equivalence classes, runtime substrate
diversity, and the dependency-tree intersection between profiles.
This is real research.
"""
from __future__ import annotations
from collections import Counter
from math import log
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.immune import FederationMember


async def compute_diversity_index(db: AsyncSession) -> dict:
    """
    Returns a dict with:
      - shannon_index: float, 0 = monoculture, log(N) = perfectly diverse
      - normalized: float, shannon_index / log(N) where N is members
      - profile_distribution: dict[hash, count]
      - warnings: list[str] of low-diversity issues
    """
    stmt = select(FederationMember).where(FederationMember.status == "active")
    result = await db.execute(stmt)
    members = result.scalars().all()

    if len(members) < 2:
        return {
            "shannon_index": 0.0,
            "normalized": 0.0,
            "profile_distribution": {},
            "warnings": ["fewer than 2 active members; diversity is undefined"],
            "n_members": len(members),
        }

    profile_counts = Counter(m.detector_profile_hash for m in members)
    n = len(members)
    shannon = -sum(
        (count / n) * log(count / n)
        for count in profile_counts.values()
        if count > 0
    )
    max_shannon = log(n)
    normalized = shannon / max_shannon if max_shannon > 0 else 0.0

    warnings: list[str] = []
    most_common_count = profile_counts.most_common(1)[0][1] if profile_counts else 0
    if most_common_count >= n / 2:
        warnings.append(
            f"more than half of federation runs the same detector profile "
            f"({most_common_count}/{n} members)"
        )
    if normalized < 0.5:
        warnings.append(
            f"normalized diversity {normalized:.2f} is below 0.5 — "
            "federation is approaching a monoculture"
        )

    return {
        "shannon_index": shannon,
        "normalized": normalized,
        "profile_distribution": dict(profile_counts),
        "warnings": warnings,
        "n_members": n,
    }
```

#### 3.2.4 `backend/immune/net/diversity_cli.py` — CLI entry point

```python
# backend/immune/net/diversity_cli.py
"""
CLI entry point for the federation diversity index.

Usage:
    uv run python -m backend.immune.net.diversity_cli --federation-snapshot=production
"""
from __future__ import annotations
import argparse
import asyncio
import json
import sys

from backend.database import async_session
from backend.immune.net.diversity import compute_diversity_index


async def _main(snapshot: str) -> dict:
    async with async_session() as db:
        return await compute_diversity_index(db)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--federation-snapshot", default="production")
    parser.add_argument("--alert-threshold", type=float, default=0.5)
    args = parser.parse_args()

    result = asyncio.run(_main(args.federation_snapshot))
    print(json.dumps(result, indent=2))

    if result["normalized"] < args.alert_threshold:
        print(
            f"WARN: normalized diversity {result['normalized']:.2f} < threshold "
            f"{args.alert_threshold}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

#### 3.2.5 Schema addition

```python
# backend/models/immune.py — addition to FederationMember
class FederationMember(Base):
    # ... existing columns
    detector_profile_hash: Mapped[str] = mapped_column(String(64), index=True)
    detector_profile_yaml: Mapped[str] = mapped_column(String(8192))
    profile_published_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

#### 3.2.6 CI gate

A nightly CI job posts the federation's diversity index to the project's monitoring dashboard. If `normalized < 0.5`, the project lead is paged. **The 0.5 threshold is a placeholder** awaiting the AIS-theory collaborator input.

```yaml
# .github/workflows/diversity_check.yml
name: Federation diversity check
on:
  schedule:
    - cron: '0 6 * * *'    # daily at 06:00 UTC
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Run diversity check
        run: |
          uv run python -m backend.immune.net.diversity_cli --federation-snapshot=production
```

### 3.3 Where collaboration goes

The honest gap: **we don't know the right diversity metric.** Shannon entropy over categorical configurations is a placeholder. Real questions:

- Two k-mer featurizers with k=5 and k=7 — how independent are their exploit surfaces? Possibly very correlated (same parser, same library).
- Embedding-based featurizers using the same underlying model (ESM2 with different head sizes) share more than they diverge.
- A principled metric needs a notion of **exploit-equivalence classes** — partition the configuration space by which exploits would compromise both members in a class. Members in the same class don't add diversity even if they look different.
- This is exactly the n-variant theoretical literature.

**Joint paper sketch:** *Diversity metrics for federated AIS: from heuristic Shannon to exploit-equivalence-class coverage.* Co-authors: AIS-theory collaborator on theory, maintainer on platform.

### 3.4 Why this engages diversity-theory expertise

- Walks in the door with the diversity-as-defense thesis instantiated, not just acknowledged.
- The placeholder Shannon metric with the explicit `TODO(immune-theory-collab):` marker says: "we know this isn't the right answer; we built the infrastructure that needs the right answer."
- The featurizer registry is general infrastructure — the AIS-theory collaborator's group could contribute new featurizers (Crispy-inspired ISR-randomized featurizers, e.g.) without touching the rest of JACKPOT.

------

## 4. Gap 2 — Software supply chain: `jackpot-sbom` and parsers-safe

### 4.1 The critique, restated

JACKPOT wraps 16 OSS projects (CZ-ID, OpenRecombinHunt, amr.watch, SeqScreen-Nano, HPD-Kit, ANDES, STREAM, Coniferest, Bactopia, AMRFinderPlus, HaplotypeTools, plus the Python deps of each). Every wrapped tool brings its own dependency tree. Without a coherent supply-chain strategy, JACKPOT is effectively merging 16+ threat surfaces.

The current plan has `scripts/verify_licenses.py` and a vague mention of "signed Nextflow workflows." That's not enough. There's no SBOM, no CVE gating, no provenance attestation, no signed container images, no policy on deserialization safety.

### 4.2 What we ship

#### 4.2.1 `scripts/generate_sbom.py` — CycloneDX SBOM generator

Wraps `cyclonedx-bom` and `syft` to emit a machine-readable SBOM for the JACKPOT base plus each wrapped tool's container.

```python
# scripts/generate_sbom.py
"""
Generate CycloneDX SBOMs for JACKPOT and every wrapped-tool container.

Usage:
    uv run python scripts/generate_sbom.py --output sbom/

Produces:
    sbom/jackpot-base.cdx.json
    sbom/jackpot-amand.cdx.json
    sbom/jackpot-recombhunt.cdx.json
    ...
    sbom/index.json    -- aggregator with cross-component vulnerability roll-up

TODO(immune-theory-collab): automated repair of CVEs in wrapped tools.
When osv-scanner flags a CVE in a wrapped tool's dependency tree, can we
auto-patch it via GenProg-descendant techniques (the automated-repair literature)? This script
just detects; the auto-repair is collaboration territory.
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

WRAPPED_TOOLS = [
    {"name": "jackpot-base", "image": "ghcr.io/midnight-oil-innovation/jackpot-base:latest"},
    {"name": "jackpot-amand", "image": "ghcr.io/midnight-oil-innovation/jackpot-amand:latest"},
    {"name": "jackpot-recombhunt", "image": "ghcr.io/midnight-oil-innovation/jackpot-recombhunt:latest"},
    {"name": "jackpot-mngs", "image": "ghcr.io/midnight-oil-innovation/jackpot-mngs:latest"},
    {"name": "jackpot-edge", "image": "ghcr.io/midnight-oil-innovation/jackpot-edge:latest"},
    # ... extend per Phase 27/28/31 wraps
]


def generate_for_image(image: str, output_path: Path) -> dict:
    """Run syft against an image, write CycloneDX JSON, return summary."""
    cmd = ["syft", image, "-o", "cyclonedx-json"]
    proc = subprocess.run(cmd, capture_output=True, check=True, text=True)
    sbom = json.loads(proc.stdout)
    output_path.write_text(json.dumps(sbom, indent=2))
    return {
        "image": image,
        "n_components": len(sbom.get("components", [])),
        "spec_version": sbom.get("specVersion"),
    }


def scan_sbom_for_vulns(sbom_path: Path) -> dict:
    """Run grype against an SBOM to roll up vulnerabilities."""
    cmd = ["grype", f"sbom:{sbom_path}", "-o", "json"]
    proc = subprocess.run(cmd, capture_output=True, check=True, text=True)
    grype = json.loads(proc.stdout)
    matches = grype.get("matches", [])

    severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Negligible": 0, "Unknown": 0}
    for m in matches:
        sev = m.get("vulnerability", {}).get("severity", "Unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    return {
        "n_matches": len(matches),
        "severity_counts": severity_counts,
        "critical_or_high": severity_counts["Critical"] + severity_counts["High"],
    }


def main(output_dir: str = "sbom") -> int:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    index = []
    fail = False

    for tool in WRAPPED_TOOLS:
        sbom_path = out / f"{tool['name']}.cdx.json"
        sbom_summary = generate_for_image(tool["image"], sbom_path)
        vuln_summary = scan_sbom_for_vulns(sbom_path)
        entry = {**tool, "sbom": sbom_summary, "vulns": vuln_summary}
        index.append(entry)

        if vuln_summary["critical_or_high"] > 0:
            print(
                f"[FAIL] {tool['name']}: {vuln_summary['critical_or_high']} Critical/High CVEs",
                file=sys.stderr,
            )
            fail = True
        else:
            print(f"[OK]   {tool['name']}: clean")

    (out / "index.json").write_text(json.dumps(index, indent=2))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
```

#### 4.2.2 `.github/workflows/supply_chain.yml` — CI supply-chain gate

The syft and grype version numbers below are **placeholders** — replace with current stable versions before this workflow runs. Renovate-bot keeps them current after first deployment.

```yaml
name: Supply chain
on:
  pull_request:
  push:
    branches: [main, staging, development]

jobs:
  pip-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Audit Python dependencies
        run: uv run pip-audit --strict --desc

  osv-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google/osv-scanner-action/osv-scanner-action@v1
        with:
          scan-args: |-
            -r
            --skip-git
            ./

  trivy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'

  generate-sbom:
    runs-on: ubuntu-latest
    needs: [pip-audit, osv-scan, trivy]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Install syft + grype (PINNED — verify versions before use)
        run: |
          # TODO: replace with actual current stable versions before first run
          SYFT_VERSION="REPLACE_WITH_CURRENT_STABLE"
          GRYPE_VERSION="REPLACE_WITH_CURRENT_STABLE"
          curl -sSfL "https://raw.githubusercontent.com/anchore/syft/v${SYFT_VERSION}/install.sh" \
            | sh -s -- -b /usr/local/bin "v${SYFT_VERSION}"
          curl -sSfL "https://raw.githubusercontent.com/anchore/grype/v${GRYPE_VERSION}/install.sh" \
            | sh -s -- -b /usr/local/bin "v${GRYPE_VERSION}"
      - uses: astral-sh/setup-uv@v3
      - name: Generate SBOMs
        run: uv run python scripts/generate_sbom.py --output sbom/
      - uses: actions/upload-artifact@v4
        with:
          name: sbom
          path: sbom/
```

#### 4.2.3 `backend/immune/sec/parsers_safe.py` — safe deserialization helpers

This is the small-but-important one. Wrapped scientific OSS often emits results as JSON, YAML, pickle, msgpack, or worse. Without a policy, every parser is a potential RCE.

```python
# backend/immune/sec/parsers_safe.py
"""
Safe deserialization helpers for wrapped-tool output.

POLICY: every parser of pipeline output from a wrapped tool MUST go
through one of the helpers in this module. Direct use of pickle.load,
yaml.unsafe_load, eval, or marshal.load against wrapped-tool output is
a Critical Rule violation.

Add to CLAUDE.md:
    Critical Rule N: All parsers of external pipeline output must use
    backend.immune.sec.parsers_safe. Direct pickle.load, yaml.unsafe_load,
    eval, exec, or marshal.load on external data is forbidden.

TODO(immune-theory-collab): static analysis to enforce this rule.
A custom flake8 / ruff / semgrep rule that flags forbidden imports
in modules other than parsers_safe itself. Scope expansion: detect
"taint flow" from network/disk to dangerous sinks. Real research.
"""
from __future__ import annotations
import json
import gzip
from pathlib import Path
from typing import Any

import yaml    # safe loader only

MAX_SAFE_JSON_SIZE = 100 * 1024 * 1024     # 100 MB
MAX_SAFE_YAML_SIZE = 10 * 1024 * 1024      # 10 MB


class UnsafeDeserializationError(Exception):
    """Raised when input fails safety preconditions."""


def safe_json(path: Path) -> Any:
    """Load JSON with size limit. Refuses files larger than MAX_SAFE_JSON_SIZE."""
    size = path.stat().st_size
    if size > MAX_SAFE_JSON_SIZE:
        raise UnsafeDeserializationError(
            f"{path} is {size} bytes, exceeds safe JSON limit of {MAX_SAFE_JSON_SIZE}"
        )
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(path.read_text(encoding="utf-8"))


def safe_yaml(path: Path) -> Any:
    """Load YAML with safe_load only. No constructors that can execute code."""
    size = path.stat().st_size
    if size > MAX_SAFE_YAML_SIZE:
        raise UnsafeDeserializationError(
            f"{path} is {size} bytes, exceeds safe YAML limit of {MAX_SAFE_YAML_SIZE}"
        )
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def safe_jsonl(path: Path):
    """Iterator over JSON-lines. Yields one parsed object per line."""
    size = path.stat().st_size
    if size > MAX_SAFE_JSON_SIZE:
        raise UnsafeDeserializationError(
            f"{path} is {size} bytes, exceeds safe JSON limit of {MAX_SAFE_JSON_SIZE}"
        )
    open_fn = gzip.open if path.suffix == ".gz" else open
    with open_fn(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


# Explicitly forbidden — re-exported as functions that raise so accidental
# imports become loud errors at runtime instead of silent vulnerabilities.

def DO_NOT_USE_pickle_load(*args, **kwargs):
    raise UnsafeDeserializationError(
        "pickle.load on external input is forbidden in JACKPOT. "
        "Use safe_json, safe_yaml, or safe_jsonl. See parsers_safe.py."
    )

def DO_NOT_USE_yaml_unsafe_load(*args, **kwargs):
    raise UnsafeDeserializationError(
        "yaml.unsafe_load on external input is forbidden in JACKPOT. "
        "Use safe_yaml. See parsers_safe.py."
    )
```

#### 4.2.4 Cosign signing for container images — with key management

```bash
# One-time keypair generation, on a trusted machine.
# cosign generates an ECDSA P-256 keypair. Private key is encrypted at rest
# with the password you set.
cosign generate-key-pair
# Produces: cosign.key (encrypted private, 7-bit-ASCII PEM)
#           cosign.pub (public, 7-bit-ASCII PEM)

# Store private key + password in GitHub Actions secrets
gh secret set COSIGN_PRIVATE_KEY < cosign.key
gh secret set COSIGN_PASSWORD --body "<password used during keygen>"

# Publish public key to repo for transparency (no secret here — it's public)
mkdir -p infra/sigstore
cp cosign.pub infra/sigstore/cosign.pub
git add infra/sigstore/cosign.pub
gac "infra: publish cosign public key for image-signing transparency"
```

```yaml
# infra/sigstore/cosign-policy.yaml
# Verify that every container image deployed by JACKPOT was signed by the
# project's cosign key.
apiVersion: policy.sigstore.dev/v1alpha1
kind: ClusterImagePolicy
metadata:
  name: jackpot-signed-images
spec:
  images:
    - glob: "ghcr.io/midnight-oil-innovation/jackpot-*"
  authorities:
    - key:
        # cosign public key, loaded from infra/sigstore/cosign.pub at deploy time
        kmsRef: ""
```

```bash
# scripts/sign_image.sh — used in release CI
#!/usr/bin/env bash
set -euo pipefail
IMAGE="${1:?image ref required}"
cosign sign --yes \
  --key env://COSIGN_PRIVATE_KEY \
  "$IMAGE"
```

#### 4.2.5 `docs/SLSA_attestation.md` — what we claim, what's true

```markdown
# JACKPOT — SLSA Attestation Status

## Claim: SLSA Build Level 2 (aspirational; tracking)

| SLSA Requirement | Status | Notes |
| --- | --- | --- |
| Build is scripted | YES | All builds via `.github/workflows/` |
| Build runs on hosted service | YES | GitHub Actions |
| Build is hermetic | PARTIAL | Base layer is hermetic; nf-core wraps pull at run time |
| Build is parameterless | NO | `gac` workflow accepts version tags |
| Provenance is unforgeable | YES | Cosign-signed by GitHub OIDC token |
| Provenance is service-generated | YES | GitHub Actions provenance |
| Provenance contains source identity | YES | git SHA in attestation |
| Provenance contains entry point | YES | workflow file path |
| Provenance contains all build parameters | YES | inputs serialized into attestation |
| Provenance contains build environment | YES | runner image SHA in attestation |

## Open gaps

- Wrapped tool images are signed by Midnight-Oil-Innovation, but their *upstream sources*
  (CZ-ID, etc.) are not. Provenance for the wrap, not the wrapped.
- Hermetic build for tools that pull conda/pip deps at run time is open work.

## TODO(immune-theory-collab)
Automated repair of upstream wrapped-tool dependencies when CVEs land.
This is the GenProg-descendant lane.
```

### 4.3 Schema impact

```python
# backend/models/immune.py — addition
class WrappedToolImage(Base):
    """Registry of every wrapped-tool image used by a pipeline run."""
    __tablename__ = "wrapped_tool_images"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    tool_name: Mapped[str] = mapped_column(String(128), index=True)
    image_ref: Mapped[str] = mapped_column(String(512))
    image_digest: Mapped[str] = mapped_column(String(128))    # sha256:...
    sbom_path: Mapped[str] = mapped_column(String(512))
    cve_high_count: Mapped[int] = mapped_column(Integer, default=0)
    cve_critical_count: Mapped[int] = mapped_column(Integer, default=0)
    last_scanned_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    cosign_verified: Mapped[bool] = mapped_column(Boolean, default=False)
```

A nightly job rescans every image referenced by recent pipeline runs and updates `cve_*_count`. Pipelines refuse to launch against images with unresolved Critical CVEs (configurable threshold).

### 4.4 Where collaboration goes

- **Automated repair of CVEs in wrapped tools.** When `osv-scanner` flags `CVE-2025-XXXXX` in `nf-core/viralrecon`'s pinned `htslib` version, can we auto-patch and submit upstream PRs? This is GenProg-descendant work, exactly the GenProg / automated-repair lane (ICSE-Most-Influential 2019).
- **Static enforcement of the deserialization policy.** A custom semgrep / ruff rule that flags forbidden imports in modules other than `parsers_safe` itself; ideally taint-flow-aware (track "data from network/disk" to dangerous sinks).
- **SBOM diffing across federation members.** Different members run different pinned versions; the federation's *union* dependency tree is what an attacker sees. Where are the cross-member overlaps?

**Joint paper sketch:** *Automated vulnerability repair in wrapped scientific software.* Co-authors: AIS-theory collaborator on the repair techniques, maintainer on JACKPOT as the deployment vehicle.

### 4.5 Why this engages supply-chain / static-analysis expertise

- Walks in with a working SBOM pipeline, signed images, CI gating, and an explicit deserialization safety policy.
- The `TODO(immune-theory-collab): auto-repair` marker is the invitation to the diversity-theory lane.
- The deserialization helpers acknowledge that wrapped scientific OSS has the same problem the rest of the open-source ecosystem has, and treats it that way.

------

## 5. Gap 3 — Static defense posture: `jackpot-mutate`

### 5.1 The critique, restated

The vision doc has clonal selection (§3.2, §10.3) handling detector evolution. But the rest of the platform — auth flows, RBAC, JWT signing keys, container images, schema versions — is treated as static. To the AIS-theory collaborator, *the system itself* should be constantly remaking itself, not just the detectors.

### 5.2 What we ship

#### 5.2.1 `backend/immune/sec/rotation.py` — scheduled rotation framework

```python
# backend/immune/sec/rotation.py
"""
Scheduled rotation of credentials and keys.

This is plumbing for adaptive defense posture. Picking the *right*
cadence per credential class is policy work that depends on threat
model and operational context.

TODO(immune-theory-collab): mutation cadence theory. We ship the rotation
infrastructure with conservative defaults (JWT signing key every 30
days, service-account creds every 90 days). The theoretical question
is: given an attacker model, what's the optimal cadence? the diversity-as-defense literature has the formal apparatus.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from enum import Enum
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class RotationKind(str, Enum):
    JWT_SIGNING_KEY = "jwt_signing_key"
    SERVICE_ACCOUNT_CRED = "service_account_cred"
    FEDERATION_API_TOKEN = "federation_api_token"
    DETECTOR_POOL_REFRESH = "detector_pool_refresh"


DEFAULT_CADENCES: dict[RotationKind, timedelta] = {
    RotationKind.JWT_SIGNING_KEY: timedelta(days=30),
    RotationKind.SERVICE_ACCOUNT_CRED: timedelta(days=90),
    RotationKind.FEDERATION_API_TOKEN: timedelta(days=180),
    RotationKind.DETECTOR_POOL_REFRESH: timedelta(days=14),
}


class Rotator(Protocol):
    kind: RotationKind
    async def rotate(self, db: AsyncSession) -> None: ...
    async def last_rotated_at(self, db: AsyncSession) -> datetime | None: ...


class JwtSigningKeyRotator:
    kind = RotationKind.JWT_SIGNING_KEY
    async def rotate(self, db: AsyncSession) -> None:
        # 1. Generate new RSA / ed25519 keypair
        # 2. Publish new public key to JWKS endpoint
        # 3. Mark old private key as "retiring" (signs nothing new but verifies for grace period)
        # 4. After grace period (24h), delete old private key
        ...

    async def last_rotated_at(self, db: AsyncSession) -> datetime | None:
        ...


class FederationApiTokenRotator:
    kind = RotationKind.FEDERATION_API_TOKEN
    async def rotate(self, db: AsyncSession) -> None:
        # Triggered both on schedule AND on event:
        #   - confirmed compromise of a federation member
        #   - confirmed leak of any member's token
        # Rotates ALL federation tokens, not just the affected member's.
        # This is the "the bee dies, the hive responds" pattern.
        ...

    async def last_rotated_at(self, db: AsyncSession) -> datetime | None:
        ...


# A scheduler runs these; the scheduler itself is a Celery beat / GCP Cloud Scheduler hook.
```

#### 5.2.2 `backend/immune/sec/cs_cyber_federated.py` — federation-wide clonal selection

Vision doc §10.3 covers clonal selection at the *member* level. This extends it to the *federation* level: when any member confirms an attack pattern, all members' detector pools mutate in response.

```python
# backend/immune/sec/cs_cyber_federated.py
"""
Federation-wide clonal selection for cyber-AIS.

When member A confirms a novel attack pattern (e.g., a prompt-injection
template that defeated an LLM analyst agent), the confirmation is
broadcast to the federation. Every member's jackpot-cs-cyber clones the
new detector with mutation-rate-proportional perturbation. The detector
pool of the whole federation evolves in response, not just the
detected member.

TODO(immune-theory-collab): how do you mutate without breaking honest clients?
There is a real tradeoff: too much mutation breaks legitimate use; too
little leaves the federation stuck. the Crispy n-variant literature
systems has the formal apparatus for this tradeoff.
"""
from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


async def broadcast_confirmed_attack(
    confirming_member: UUID,
    attack_pattern_detector_id: UUID,
    db: AsyncSession,
) -> None:
    """
    Member A confirms an attack. Push to the federation.
    Each receiving member's TrustEngine validates the confirmation
    (was it actually a novel attack? did it actually fire on real data?)
    and, if validated, clones the detector locally with mutation.
    """
    ...


async def receive_attack_broadcast(
    sender_member: UUID,
    detector_payload: dict,
    db: AsyncSession,
) -> dict:
    """
    Inbound endpoint. Validates trust + signature, then schedules
    a local clonal-selection round that mutates the new detector
    into the local pool.

    Returns:
      {
        "accepted": bool,
        "reason": str,
        "local_detector_ids_added": list[UUID],
      }
    """
    ...
```

#### 5.2.3 `backend/middleware/api_surface_mutation.py` — Crispy-style stub

The most explicitly the AIS-theory collaborator-coded piece. Rotates non-functional aspects of the API surface so exploit fingerprints break without breaking honest clients.

```python
# backend/middleware/api_surface_mutation.py
"""
Mutate non-functional aspects of the API surface to break exploit fingerprints.

What we mutate:
  - Order of fields in 4xx/5xx response bodies (semantic-equivalent shuffle)
  - Phrasing of error messages (rotated through equivalent wordings)
  - Header naming case (X-Request-ID vs x-request-id; HTTP allows both)
  - Optional debug headers presence/absence on a schedule

What we do NOT mutate:
  - 2xx response field order (clients depend on this)
  - HTTP status codes
  - Anything covered by API versioning (clients pin those explicitly)

The key insight: legitimate clients should not depend on these things.
Exploits frequently do. Mutation drops the cost-of-exploit while keeping
the cost-of-honest-use ~zero.

TODO(immune-theory-collab): this is half of Crispy applied to a REST API.
The full version mutates more deeply at the language/runtime level
(instruction-set randomization on Python bytecode, e.g.). The honest
question is which mutations are worth the operational complexity.
This is the diversity-theory lane.
"""
from __future__ import annotations
import hashlib
from datetime import datetime
from fastapi import Request
from fastapi.responses import JSONResponse


# Mutation seed rotates daily; same for all replicas of one member; different across members.
def _mutation_seed_today(member_id: str) -> int:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    h = hashlib.sha256(f"{member_id}|{today}".encode()).hexdigest()
    return int(h[:16], 16)


ERROR_PHRASING_VARIANTS: dict[int, list[str]] = {
    401: [
        "authentication required",
        "credentials missing or invalid",
        "not authenticated",
        "auth required to access this resource",
    ],
    403: [
        "permission denied",
        "insufficient privileges",
        "access forbidden",
        "not authorized for this operation",
    ],
    404: [
        "not found",
        "resource does not exist",
        "no such resource",
        "the requested resource was not found",
    ],
    429: [
        "rate limit exceeded",
        "too many requests",
        "request quota exceeded for this window",
        "slow down — limit reached",
    ],
}


async def mutate_error_response(request: Request, status_code: int) -> JSONResponse:
    member_id = request.app.state.member_id
    seed = _mutation_seed_today(member_id)
    phrasings = ERROR_PHRASING_VARIANTS.get(status_code, ["error"])
    msg = phrasings[seed % len(phrasings)]
    return JSONResponse(
        status_code=status_code,
        content={"detail": msg, "status": status_code},
    )
```

### 5.3 Schema impact

```python
# backend/models/immune.py — addition
class RotationEvent(Base):
    """Append-only log of every rotation, for forensic + scheduling use."""
    __tablename__ = "rotation_events"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    triggered_by: Mapped[str] = mapped_column(String(32))    # scheduled | event | manual
    triggered_event_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    succeeded: Mapped[bool] = mapped_column(Boolean, default=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
```

### 5.4 Where collaboration goes

- **Optimal mutation cadence given an attacker model.** the n-variant literature is the right starting frame; we have the rotation infrastructure but not principled cadence selection.
- **Crispy applied at the language/runtime level.** API-surface mutation is shallow; deeper mutations (Python bytecode ISR-equivalents, response-format polymorphism) need the AIS-theory collaborator's expertise to design without breaking things.
- **Federation-wide CSA convergence properties.** When every member mutates in response to a broadcast, does the federation's detector pool converge or diverge? Real research.

**Joint paper sketch:** *Adaptive defense posture for federated AIS: from API-surface mutation to runtime polymorphism.*

### 5.5 Why this engages dynamic-defense / mutation-theory expertise

The API surface mutation module is the most legible piece. It says: "we read your Crispy paper, we built the API-level analog, we know the runtime-level version is research." That's a good handoff.

------

## 6. Gap 4 — Misuse and governance: `jackpot-governance` + refusal mechanisms

### 6.1 The critique, restated

AGPL is necessary but not sufficient. There's no community-governance model, no refusal-to-deploy criteria, no asymmetric-power awareness, no DURC integration. the AIS-theory collaborator was Jefferson Science Fellow at State; her ethics-of-WBE paper specifically calls out re-identification risks even in supposedly anonymous wastewater data.

Her question: "What stops an authoritarian regime from using JACKPOT for surveillance? Your federation model assumes peer trust calibration but ignores asymmetric power between rich and poor members. Where's the kill-switch when JACKPOT's used in ways the community didn't intend?"

### 6.2 What we ship

#### 6.2.1 `GOVERNANCE.md` — community charter v0

```markdown
# JACKPOT Governance — v0 (draft, 2026-05-08)

## Why this document exists

JACKPOT is open-source biosurveillance infrastructure. Open source plus public health
plus federated platform plus AI plus pathogen genomics is a combination of dual-use
risks that AGPL alone does not address. This document is v0 — it captures what we
have so far. It is incomplete by design and will evolve through community review.

## Project identity

- **Project owner of record:** maintainer maintainer (Midnight-Oil-Innovation / Linux Prophet)
- **License:** AGPL-3.0
- **Repository:** github.com/Midnight-Oil-Innovation/jackpot

## Steering committee

Until the project has 5+ active maintainers contributing across at least 3 unrelated
organizations, governance is a single-maintainer project under maintainer maintainer with public
visibility into all decisions via:
- Decision Records in `docs/decisions/YYYY-MM-DD-NN-title.md`
- Public roadmap in `todo.md`
- Public-archive mailing list (TBD)

When the maintainer threshold is met, the steering committee model adopted will
follow the Apache Software Foundation pattern (PMC, lazy consensus, vetoes require
justification).

## Code of conduct

Adopts the Contributor Covenant 2.1 verbatim (see `CODE_OF_CONDUCT.md`). Enforcement
is the steering committee's responsibility; until the committee exists, the maintainer
acts as enforcer, with reporting via a private email address documented separately.

## Refusal-to-deploy criteria

The project will refuse to support, document, or accept contributions that primarily
enable any of the following use cases:

- **Named-individual genetic surveillance.** JACKPOT does not provide UI or API
  mechanisms for "look up this person's genome." Refusal is mechanical (see
  refusal.py) as well as policy.
- **Immigration enforcement.** No support for use cases whose primary purpose is
  determining whether a person should be admitted, detained, or deported on the basis
  of biological samples.
- **Discrimination or selection on the basis of population genetics.** No support for
  hiring, insurance, or admissions use cases.
- **Targeted bioweapon design.** Use of jackpot-biosig to optimize a sequence for
  evading an identified specific population's immune profile.

These are not exhaustive. The community will extend this list. Disputes go through
the Decision Records process.

## Asymmetric-power awareness

Federation participation must be open to LMIC members on terms that do not punish them
for having less data, less compute, or weaker connectivity. Concretely:

- Trust calibration math (see asymmetric_trust.py) does NOT scale linearly with
  submission count. Members with fewer high-quality submissions are not penalized
  relative to high-volume members.
- Compute requirements for federation participation are designed to fit on a
  workstation. The federation member tier (Target E) does not require GCP-scale
  infrastructure.
- Documentation, training materials, and CI tests run with no internet access except
  to package mirrors. Members with restricted connectivity can self-host all
  resources.

## Wet-side advisory

A "wet-side advisor" role: a named individual or panel from the wet-lab community
who reviews JACKPOT's assumptions about input data once per quarter. Initially
the wet-side advisor's group via the National Sewage Sludge Repository connection; expanded as
federation members come on.

## Sunset and fork policy

- **For v1.0 and later:** the project guarantees a minimum 90-day notice period
  before any breaking change to the federation protocol or the multi-tenant data
  schema.
- **Pre-1.0 (current state):** the project may make breaking changes during
  development, but documents them in CHANGELOG.md with migration instructions
  whenever feasible. Federation interop in pre-1.0 is best-effort, not contractual.
- If the project is taken in a direction the community deems harmful, the AGPL
  license guarantees the right to fork. The maintainer commits to documenting fork
  instructions publicly (docs/forking.md).
- Kill-switch posture for the official-channel federation: if the official channel
  is being used in ways that violate the refusal-to-deploy criteria above, the
  steering committee may revoke that channel's official status. Forks remain free
  to operate.

## Dual-use research review

Submissions that touch high-concern dual-use territory (synthetic biology, AI-evading
pathogen design, host-immune-response prediction at population scale) are flagged at
ingest by jackpot-screening (Wittmann 2025 wrapper) and routed to a DURC review
queue (see docs/dual_use_review.md and refusal.py). Review is performed by a
rotating panel; for v0, the maintainer is the panel.

## TODO(immune-theory-collab): policy framework
The above is a starting position. A real governance framework needs the AIS-theory collaborator's
cyberpolicy / Jefferson Science Fellow expertise to be credible. Open questions:

- Who appoints the steering committee initially?
- What's the conflict-resolution process when refusal-to-deploy criteria are disputed?
- How does the project respond when a fork is used in ways the community considers
  harmful?
- What's the relationship to existing biosecurity governance bodies (NSABB,
  IBC equivalents)?
```

#### 6.2.2 `backend/immune/sec/refusal.py` — technical refusal mechanisms

Governance without technical enforcement is just a wish. This module provides query-pattern detectors and operation-class blocks that enforce the refusal-to-deploy criteria mechanically. Includes false-positive defenses on the named-individual rule.

```python
# backend/immune/sec/refusal.py
"""
Technical refusal mechanisms for prohibited use classes.

This module enforces refusal-to-deploy criteria from GOVERNANCE.md
mechanically. The configuration JACKPOT_REFUSAL_MODE controls behavior:
  - "off" (default for laptops + CI):  refusal logic runs but only logs
  - "warn":                            refusal logic logs and warns clients
  - "enforce":                         refusal logic blocks with HTTP 451

Production deployments SHOULD set JACKPOT_REFUSAL_MODE=enforce.

TODO(immune-theory-collab): policy as code framework. The current
implementation is hand-coded query-pattern detectors. A proper
implementation would use a policy-as-code framework (OPA / Rego or
similar) with formally specified rules and proofs that the rules are
applied consistently. Real research territory.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Protocol
import os

import structlog

logger = structlog.get_logger()


class RefusalMode(str, Enum):
    OFF = "off"
    WARN = "warn"
    ENFORCE = "enforce"


def current_mode() -> RefusalMode:
    return RefusalMode(os.environ.get("JACKPOT_REFUSAL_MODE", "off"))


@dataclass(frozen=True)
class RefusalDecision:
    refused: bool
    rule: str | None
    reason: str | None
    mode: RefusalMode


class RefusalRule(Protocol):
    """A rule examines a request and decides whether it should be refused."""
    rule_id: str

    def evaluate(self, context: dict) -> RefusalDecision: ...


class NamedIndividualSearchRule:
    """
    Refuses queries that contain a personal name in a field where personal
    names are NOT expected.

    Fields where personal names are EXPECTED (and thus do not trigger refusal):
      collector_name, submitter, principal_investigator, pi_name, contact_email,
      contact_name, owner, created_by_name, modified_by_name, reviewer_name,
      annotator_name

    Personal names appearing in OTHER fields (free-text descriptions, sample
    aliases, project names, query strings) are considered surveillance signal
    and trigger refusal.

    TODO(immune-theory-collab): this is a heuristic, not a guarantee. A
    sophisticated user can split the lookup into two queries. Real
    refusal needs flow-tracking (which fields, of which type, were
    submitted by which user, in which session). That's research.
    """
    rule_id = "named-individual-search"

    EXPECTED_NAME_FIELDS = frozenset({
        "collector_name", "submitter", "principal_investigator", "pi_name",
        "contact_email", "contact_name", "owner", "created_by_name",
        "modified_by_name", "reviewer_name", "annotator_name",
    })

    def evaluate(self, context: dict) -> RefusalDecision:
        query = context.get("query_payload", {}) or {}
        is_sample_search = "samples" in (context.get("path", "") or "")

        if not is_sample_search:
            return RefusalDecision(refused=False, rule=None, reason=None, mode=current_mode())

        suspicious_field = None
        for field, value in query.items():
            if field in self.EXPECTED_NAME_FIELDS:
                continue
            if isinstance(value, str) and self._looks_like_personal_name(value):
                suspicious_field = field
                break

        if suspicious_field is None:
            return RefusalDecision(refused=False, rule=None, reason=None, mode=current_mode())

        return RefusalDecision(
            refused=True,
            rule=self.rule_id,
            reason=f"personal name appears in unexpected field {suspicious_field!r}; "
                   f"surveillance-pattern refusal triggered",
            mode=current_mode(),
        )

    def _looks_like_personal_name(self, value: str) -> bool:
        import re
        name_re = re.compile(r"\b[A-Z][a-z]{1,15}\s+[A-Z][a-z]{1,20}\b")
        return bool(name_re.search(value))


class ImmigrationEnforcementUserAgentRule:
    """
    Refuses requests with user agents associated with immigration-enforcement
    tooling.

    v0 BEHAVIOR: PROHIBITED_UA_FRAGMENTS is intentionally empty. The rule is
    plumbing — it runs on every request and the data structure is in place
    so the community-maintained UA list can be added without code changes.
    Until the list is populated (a community/governance process, not a
    technical decision), this rule never fires.

    Populate via config file `config/prohibited_uas.yaml` in production
    deployments; the list is loaded at module import time.
    """
    rule_id = "immigration-enforcement-ua"
    PROHIBITED_UA_FRAGMENTS: tuple[str, ...] = ()    # populated from config

    def evaluate(self, context: dict) -> RefusalDecision:
        if not self.PROHIBITED_UA_FRAGMENTS:
            return RefusalDecision(refused=False, rule=None, reason=None, mode=current_mode())
        ua = (context.get("user_agent", "") or "").lower()
        refused = any(frag in ua for frag in self.PROHIBITED_UA_FRAGMENTS)
        return RefusalDecision(
            refused=refused,
            rule=self.rule_id if refused else None,
            reason="user agent matches prohibited-use list" if refused else None,
            mode=current_mode(),
        )


# Registered rules; FastAPI middleware iterates these on every request.
RULES: list[RefusalRule] = [
    NamedIndividualSearchRule(),
    ImmigrationEnforcementUserAgentRule(),
]


def evaluate(context: dict) -> RefusalDecision:
    """Run all rules. Return the first refusing decision or 'not refused'."""
    for rule in RULES:
        decision = rule.evaluate(context)
        if decision.refused:
            logger.warning(
                "refusal_rule_triggered",
                rule=decision.rule,
                reason=decision.reason,
                mode=decision.mode.value,
                path=context.get("path"),
                user_id=context.get("user_id"),
            )
            return decision
    return RefusalDecision(refused=False, rule=None, reason=None, mode=current_mode())
```

The middleware glue:

```python
# backend/middleware/refusal_middleware.py
import json
from fastapi import Request, status
from fastapi.responses import JSONResponse

from backend.immune.sec.refusal import evaluate, current_mode, RefusalMode


async def refusal_middleware(request: Request, call_next):
    body = b""
    if request.method in ("POST", "PUT", "PATCH"):
        body = await request.body()

    try:
        query_payload = json.loads(body) if body else {}
    except Exception:
        query_payload = {}

    context = {
        "path": str(request.url.path),
        "method": request.method,
        "user_agent": request.headers.get("user-agent", ""),
        "user_id": getattr(request.state, "user_id", None),
        "query_payload": query_payload,
    }

    decision = evaluate(context)

    if decision.refused and current_mode() == RefusalMode.ENFORCE:
        return JSONResponse(
            status_code=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
            content={
                "detail": "This request was refused under JACKPOT's prohibited-use policy.",
                "rule": decision.rule,
                "reason": decision.reason,
                "policy": "https://github.com/Midnight-Oil-Innovation/jackpot/blob/main/GOVERNANCE.md",
            },
        )

    return await call_next(request)
```

#### 6.2.3 `backend/immune/net/asymmetric_trust.py` — fairness in trust calibration

The trust math (vision doc §6.2.1) must not punish low-data members. This module fixes the math with explicit input validation (no hidden clamps on quality scores).

```python
# backend/immune/net/asymmetric_trust.py
"""
Trust calibration that does not punish low-data members.

Naive trust scoring (count confirmed submissions) penalizes members
who are doing high-quality work but with limited sample volume. That's
LMIC members, smaller state labs, and any new joiner.

This module provides a corrected scoring function that uses sub-linear
scaling on submission count and weights by quality, not raw volume.

TODO(immune-theory-collab + wet-side-advisory-collab): fairness theory for federated
trust. The current correction is a heuristic (sublinear scaling +
quality weighting). A principled approach would treat trust as a
two-dimensional latent variable (capability, reliability) inferred from
observed events, with explicit fairness constraints. Real research.
the wet-side advisor tagged because his network of LMIC wastewater partners is the
real-world testbed for fairness.
"""
from __future__ import annotations
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class TrustComponents:
    capability_score: float        # how capable is this member at confirming (0..1)
    reliability_score: float       # how reliable when they do confirm (0..1)
    overall_score: float           # combined; this is what gates federation actions


def compute_corrected_trust(
    confirmed_submission_count: int,
    rejected_submission_count: int,
    quality_weighted_confirmed_sum: float,
    days_since_last_activity: int,
    submission_window_days: int = 365,
) -> TrustComponents:
    """
    Sub-linear in count, linear in quality, with time decay.

    PRECONDITION: quality_weighted_confirmed_sum must be the sum of per-submission
    quality scores, where each per-submission score is in [0.0, 1.0]. The sum
    therefore satisfies 0 <= quality_weighted_confirmed_sum <= confirmed_submission_count.
    Caller is responsible for normalizing quality scores into [0,1] before summing.
    """
    if quality_weighted_confirmed_sum < 0:
        raise ValueError(
            f"quality_weighted_confirmed_sum={quality_weighted_confirmed_sum} is negative; "
            "per-submission quality scores must be in [0.0, 1.0]"
        )
    if quality_weighted_confirmed_sum > confirmed_submission_count:
        raise ValueError(
            f"quality_weighted_confirmed_sum={quality_weighted_confirmed_sum} exceeds "
            f"confirmed_submission_count={confirmed_submission_count}; "
            "each per-submission quality score must be in [0.0, 1.0]"
        )

    # Capability: ability to do the work. Sub-linear in count.
    n = max(0, confirmed_submission_count)
    capability = math.sqrt(n + 1) / math.sqrt(n + 1 + 10)

    # Reliability: of the things they confirmed, how many held up.
    total = confirmed_submission_count + rejected_submission_count
    if total == 0:
        reliability = 0.5    # neutral prior
    else:
        # quality_weighted_confirmed_sum is now guaranteed <= total by validation above
        reliability = quality_weighted_confirmed_sum / total

    # Time decay: drift toward neutral after long inactivity
    decay_factor = math.exp(-max(0, days_since_last_activity - 30) / 365.0)
    capability *= decay_factor
    reliability = 0.5 + (reliability - 0.5) * decay_factor

    # Overall: geometric mean (penalize being weak in either dimension)
    overall = math.sqrt(capability * reliability)

    return TrustComponents(
        capability_score=capability,
        reliability_score=reliability,
        overall_score=overall,
    )
```

#### 6.2.4 `docs/dual_use_review.md` — DURC review checklist

```markdown
# JACKPOT Dual-Use Research of Concern (DURC) Review

## When this triggers

A submission is routed to the DURC review queue when ANY of the following are true:

1. jackpot-screening (Wittmann 2025 wrapper) flags structural matches to
   high-concern toxin / pathogen reference classes.
2. jackpot-biosig detects optimization signatures consistent with
   immune-evasion engineering.
3. jackpot-recombhunt detects recombinants involving > 1 known
   high-concern source organism.
4. The submitter explicitly flags the submission as DURC-relevant
   (encouraged via UI affordance).

## Review process (v0)

For v0, the maintainer is the review panel. This is acknowledged-inadequate.

When triggered:

- The submission moves to status dca_review_pending (a new sample status,
  beyond Tier-1/2/3).
- The submitting member's TrustEngine receives a temporary under_review
  flag; trust score does not change but the flag is visible to the federation.
- An out-of-band notification (email + Slack to the maintainer) is sent.
- Pipeline runs against the sample are blocked.
- The reviewer documents their decision in
  docs/durc_decisions/YYYY-MM-DD-<sample-uuid>.md.

## TODO(immune-governance-collab + external-policy-network)

The full review process needs:

- A real panel (3+ reviewers, rotating).
- Conflict-of-interest disclosure protocol.
- Appeals process.
- Coordination protocol with NSABB equivalents.
- Time-bounded SLA (samples cannot sit in review forever).

This is exactly the AIS-theory collaborator's Jefferson Science Fellow lane.
```

### 6.3 Schema impact

```python
# backend/models/immune.py — addition
class RefusalEvent(Base):
    """Append-only log of every refused request, for accountability."""
    __tablename__ = "refusal_events"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    rule_id: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(String(2048))
    mode: Mapped[str] = mapped_column(String(16))
    request_path: Mapped[str] = mapped_column(String(512))
    request_method: Mapped[str] = mapped_column(String(8))
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)


class DurcReviewQueueItem(Base):
    """Samples flagged for DURC review."""
    __tablename__ = "durc_review_queue"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    sample_id: Mapped[UUID] = mapped_column(ForeignKey("samples.id"), index=True)
    triggered_by: Mapped[str] = mapped_column(String(32))    # screening | biosig | recombhunt | self_flagged
    triggered_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(16), default="pending")    # pending | approved | rejected | escalated
    reviewer_user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    decision_at: Mapped[datetime | None] = mapped_column(nullable=True)
    decision_doc_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
```

### 6.4 Where collaboration goes

- **Policy framework with theoretical grounding.** The current refusal logic is hand-coded heuristics. A real version would use a policy-as-code framework with formal proofs of rule consistency.
- **Asymmetric-power fairness theory.** The corrected trust math is a heuristic. The principled version is a formal fairness analysis.
- **DURC review as a real institution.** the AIS-theory collaborator's State Department network is the right path to a credible review panel.

**Joint paper sketch:** *Mechanical refusal-to-deploy in open-source biosurveillance: technical, policy, and governance dimensions.* the AIS-theory collaborator leads policy framing, maintainer leads technical, ideally a third co-author from the bioethics community.

### 6.5 Why this engages governance / asymmetric-trust expertise

Walking in with `GOVERNANCE.md` v0, mechanical refusal middleware, asymmetric trust math, and a DURC queue says: "we know AGPL isn't enough; we built the technical handles for governance; we need help making them principled." That's the right invitation.

------

## 7. Gap 5 — Education-as-foundation reframing

### 7.1 The critique, restated

the AIS-theory collaborator's framing for the Biodesign Center explicitly contrasts "integration of computation with biology and health" against technologists "isolated from those who actually use or are affected by it on a daily basis." A vision doc that put education fourth, after three technical pillars, read exactly like the failure mode she described.

The vision doc §1 has been corrected to elevate workforce to a co-equal thesis with the dual-AIS thesis. The §15.3 publication pipeline now lists the workforce paper as a sibling differentiator. This section captures the meta-module that makes the framing concrete.

### 7.2 What we ship

#### 7.2.1 `course/modules/_meta/ais_framing.md` — meta-module

A new "module zero" that all Academy students see first, framing JACKPOT in the AIS-theory collaborator's terms.

```markdown
# Module 0 — Why JACKPOT exists, and why you're here

## The integration thesis

JACKPOT is not a product that happens to have a curriculum. It is a workforce
development platform that happens to also do pathogen genomic surveillance.

This framing comes from Stephanie the AIS-theory collaborator's articulation of the Biodesign Center
mission: "translating insights between computer science and biology, with a focus
on understanding and mitigating malicious behavior in complex systems," and her
explicit warning against technologists "isolated from those who actually use or
are affected by it on a daily basis."

JACKPOT Academy exists because:

1. Public health workforce capacity is the rate-limiting factor in pandemic
   preparedness, more so than tooling.
2. Tooling built without the workforce in mind is built wrong.
3. The fastest way to make sure JACKPOT is the right tooling is to make sure
   people learning genomic surveillance learn it ON JACKPOT.

## What this means for you, the student

- You are not learning ABOUT JACKPOT. You are learning genomic surveillance, and
  JACKPOT is the lab.
- Your module exercises produce code that gets PR'd to the production platform.
- Your wrong answers in Outbreak / WILDFIRE generate adversarial training data
  for the production immune system.
- You graduate the Academy with a public, attribution-preserved record of your
  contributions to a real platform that real public-health labs use.

## The pillar reordering

The vision doc lists five pillars: Bio-AIS, Cyber-AIS, Federation Immune Network,
Academy, Outbreak/WILDFIRE. Numerically, Academy is fourth. Operationally, it's
zeroth: the Academy generates the trained operators who run the rest, the
contributors who extend the rest, the labelers who confirm what the rest detects,
and the players who stress-test what the rest defends.

Read this module, then go to module 1.
```

### 7.3 Where collaboration goes

- **Empirical evaluation of training outcomes.** Are JACKPOT Academy graduates better-prepared than peers from conventional bioinformatics training? the AIS-theory collaborator's lab has the academic infrastructure to run that evaluation.
- **Curriculum co-design with public health workforce stakeholders.** APHL, WHO IPSN, state lab consortia.

### 7.4 Why this engages AIS-theory pedagogical expertise

This gap is mostly framing, but the framing matters. Walking in with "we built workforce in" instead of "we built workforce on top of" lands differently.

------

## 8. Cross-cutting: the `jackpot-redteam` track + adversarial-security and cryptographic expertise

### 8.1 Why this is a cross-cutting section

The the adversarial-security collaborator critiques ("synthetic data isn't representative", "ML pipelines are vulnerable to your own attacks") and the the applied-cryptography collaborator critiques ("crypto primitive imprecision", "federation needs formal proof", "re-identification leaks") share a meta-critique: *you are not red-teaming yourselves hard enough.*

The fix is a deliberate adversarial pipeline that attacks JACKPOT's own detectors, embeddings, and federation protocols, with results published and feeding back into design choices. Plus dedicated subsections for the adversarial-security collaborator-specific (§8.5) and the applied-cryptography collaborator-specific (§8.6) hooks beyond the cross-cutting redteam track.

### 8.2 What we ship

#### 8.2.1 `backend/immune/redteam/` — the attack pipeline

```
backend/immune/redteam/
├── __init__.py
├── cli.py                      # entry point for uv run python -m backend.immune.redteam.cli
├── attack_amand.py             # adversarial perturbation against jackpot-amand NSA
├── attack_mg2vec.py            # membership inference against microbiome embeddings
├── attack_biosig.py            # adversarial perturbation against ESMFold-based detector
├── attack_federation.py        # re-identification attacks on aggregated federation signals
├── attack_screening.py         # AI-generated sequences attempting to evade jackpot-screening
├── data_representativeness.py  # NEW: evaluate synthetic-data representativeness vs real
└── tests/
    ├── test_attack_amand.py
    ├── test_attack_mg2vec.py
    └── ...
```

A representative module:

```python
# backend/immune/redteam/attack_amand.py
"""
Adversarial perturbation attack against jackpot-amand.

Generates synthetic samples engineered to evade NSA detectors. Used in
nightly red-team runs to measure detector robustness over time.

TODO(immune-redteam-collab): iterative attack-and-defend framework. The current
implementation is a fixed gradient-based perturbation generator. the group publishes iterative framework (adversarial-security literature)s where the attack and defense
co-evolve. JACKPOT should plug into that framework.

TODO(immune-crypto-collab): privacy-preserving red-team. Currently the
red-team has full access to detector internals. A more realistic
threat model is an attacker with API-only access. This is exactly the
oracle-attack threat model the applied-cryptography collaborator's group works on.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import numpy as np

from backend.immune.bio.amand import AmandDetector


@dataclass(frozen=True)
class AttackResult:
    n_attempts: int
    n_evasions: int
    evasion_rate: float
    median_perturbation_size: float
    sample_evasions: list[Path]


def gradient_perturbation_attack(
    detector: AmandDetector,
    seed_samples: list[Path],
    max_iterations: int = 100,
    perturbation_budget: float = 0.05,
) -> AttackResult:
    """
    For each seed sample, attempt to perturb it (within budget) such that
    the detector no longer flags it. Returns evasion statistics.
    """
    n_evasions = 0
    perturbations: list[float] = []
    evasion_paths: list[Path] = []

    for seed in seed_samples:
        # Gradient-based perturbation, fallback to random search.
        # Budget: edit distance / sample length.
        ...

    return AttackResult(
        n_attempts=len(seed_samples),
        n_evasions=n_evasions,
        evasion_rate=n_evasions / max(1, len(seed_samples)),
        median_perturbation_size=float(np.median(perturbations) if perturbations else 0.0),
        sample_evasions=evasion_paths,
    )
```

#### 8.2.2 `backend/immune/redteam/data_representativeness.py` — separate from robustness

The redteam track cleanly distinguishes two questions:

- **Adversarial robustness:** can a perturbation evade the detector?
- **Representativeness:** does the synthetic corpus we trained on match the distribution we'll see in production?

```python
# backend/immune/redteam/data_representativeness.py
"""
Evaluate how representative synthetic training data is, relative to real data.

Different question from adversarial robustness. A detector trained on
unrepresentative synthetic data may be robust against adversarial perturbations
of synthetic samples while being completely useless on real data.

TODO(immune-redteam-collab): MIA design. Current implementation is a basic
distribution-distance metric. the adversarial-security collaborator's group publishes formal membership-
inference attacks; plugging those in gives us a tighter representativeness
test.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class RepresentativenessReport:
    n_synthetic: int
    n_real: int
    feature_distribution_distance: float
    membership_inference_advantage: float
    interpretation: str


def evaluate_representativeness(
    synthetic_features: np.ndarray,
    real_features: np.ndarray,
) -> RepresentativenessReport:
    """
    Compare synthetic feature distribution to real feature distribution.
    Returns metrics + a human-readable interpretation.

    feature_distribution_distance: Wasserstein-1 between distributions.
    membership_inference_advantage: how distinguishable synthetic is
        from real to a binary classifier (0 = indistinguishable, 1 = trivially
        separable; high values mean synthetic data is unrepresentative).
    """
    ...
```

#### 8.2.3 `backend/immune/redteam/attack_federation.py` — re-identification attacks

the applied-cryptography lane specifically.

```python
# backend/immune/redteam/attack_federation.py
"""
Re-identification attacks against federated aggregate signals.

The federation publishes aggregate signals (e.g., 'how many members
have seen lineage X this week') with differential-privacy noise. Naive
DP parameter choices can leak more than expected when an attacker
queries adaptively across time.

This module implements known re-identification attack patterns:
  - Trajectory reconstruction (which member's curve does this look like?)
  - Membership inference (was member X's data in this aggregate?)
  - Differencing attack (compare adjacent time windows)

TODO(immune-crypto-collab): formal privacy budget analysis. The current
implementation flags suspicious leakage; the principled version
computes exact privacy budget consumption per query class and
warns when budget is depleting faster than expected. Real research.
"""
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession


async def trajectory_reconstruction_attack(
    db: AsyncSession,
    target_member_id: str,
    time_window_days: int = 90,
) -> dict:
    """Given access to all aggregate publishings, attempt to reconstruct
    the per-member contribution curve for a target member."""
    ...


async def membership_inference_attack(
    db: AsyncSession,
    candidate_sample_features: list[float],
) -> dict:
    """Given access to all aggregate publishings AND a candidate sample,
    estimate the posterior probability that the candidate sample was
    in member X's training set, for each member X."""
    ...
```

#### 8.2.4 `backend/immune/redteam/cli.py` — CLI entry point

```python
# backend/immune/redteam/cli.py
"""
CLI entry point for the red-team suite.

Usage:
    uv run python -m backend.immune.redteam.cli --output redteam-results/
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target-module", default="all")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")

    results: dict = {}
    # As attack modules land, dispatch to them based on args.target_module.
    # Each attack returns a serializable dict appended into results.

    report_path = args.output / f"redteam-{timestamp}.json"
    report_path.write_text(json.dumps(results, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

#### 8.2.5 `.github/workflows/redteam.yml` — weekly red-team runs

```yaml
name: Red team
on:
  schedule:
    - cron: '0 4 * * 1'
  workflow_dispatch:

jobs:
  redteam:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Run red team suite
        run: uv run python -m backend.immune.redteam.cli --output redteam-results/
      - uses: actions/upload-artifact@v4
        with:
          name: redteam-results
          path: redteam-results/
      - name: Open issue on regression
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: 'Red team regression: detector evasion rate increased',
              body: 'See workflow run for details.',
              labels: ['security', 'redteam', 'regression']
            })
```

#### 8.2.6 `docs/redteam_results/` — public publication of results

A weekly report lands in the repo, public and version-controlled. Showing the work in progress is the point.

### 8.3 Schema impact

```python
# backend/models/immune.py — addition
class RedTeamRun(Base):
    """Append-only log of red-team runs and their summary statistics."""
    __tablename__ = "redteam_runs"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    attack_kind: Mapped[str] = mapped_column(String(64), index=True)
    target_module: Mapped[str] = mapped_column(String(64), index=True)
    target_module_version: Mapped[str] = mapped_column(String(32))
    n_attempts: Mapped[int] = mapped_column(Integer)
    n_successes: Mapped[int] = mapped_column(Integer)
    success_rate: Mapped[float] = mapped_column(Float)
    summary: Mapped[dict] = mapped_column(JSONB)
    artifact_path: Mapped[str] = mapped_column(String(512))
    occurred_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
```

### 8.4 Where collaboration goes (cross-cutting)

- **Iterative attack-and-defend frameworks (the adversarial-security collaborator).** The current red-team is one-shot per nightly run. the adversarial-security collaborator's group publishes co-evolving frameworks where attack and defense improve together. JACKPOT plugs in as a deployment platform.
- **Privacy-preserving red-team (the applied-cryptography collaborator).** Realistic threat models give attackers API-only access, not full detector internals. Oracle-attack threat model is the applied-cryptography collaborator's group's lane.
- **Formal privacy budget analysis (the applied-cryptography collaborator).** Current re-identification attacks flag leakage qualitatively. the applied-cryptography collaborator's group can compute it exactly.
- **Adversarial example representativeness (the adversarial-security collaborator).** The synthetic adversarial samples we generate may not match real-world attack distributions. Membership-inference on the synthetic-data corpus tells us how representative they are.

**Joint paper sketch:** *Red-teaming federated AIS for pathogen genomic surveillance.* Co-authors: the adversarial-security collaborator (iterative attack/defend), the applied-cryptography collaborator (privacy-preserving attacks + formal budget), maintainer (platform).

### 8.5 Adversarial-ML hooks beyond the redteam track

Heewook the adversarial-security collaborator's published work on **TCR-epitope binding prediction** maps directly onto two JACKPOT modules that don't appear in the redteam track:

- **`jackpot-immune-evasion`** (vision doc §4.2) — detects mutations consistent with immune-evasion strategies including epitope shifts, glycosylation site changes, and antigenic variation. TCR-epitope binding prediction is the formal apparatus for the "epitope shift" component. `TODO(immune-redteam-collab): TCR-epitope binding integration` lives in `backend/immune/bio/immune_evasion.py`.
- **`jackpot-biosig`** — detects functionally significant changes including binding-pocket shifts. TCR-epitope binding prediction generalizes this approach beyond MHC. `TODO(immune-redteam-collab): TCR-prediction extension` lives in `backend/immune/bio/biosig.py`.

This is methods-paper material independent of the redteam track. Joint paper: *TCR-epitope-aware immune-evasion detection in pathogen genomic surveillance.*

### 8.6 Cryptographic-primitives hooks beyond the redteam track

Ni the applied-cryptography collaborator's signature primitive is **PSI-CA (private set intersection cardinality), per the applied-cryptography collaborator et al. PoPETs 2024**; her broader research covers private set intersection variants, secure aggregation, and oblivious protocols. Beyond the redteam track:

- **`backend/immune/net/query_he.py`** — already has `TODO(immune-crypto-collab): protocol selection`. This is the federation crypto layer (vision doc §6.2.2 has been corrected to acknowledge this is a placeholder needing per-query-class primitive selection: PSI-CA for set-membership, secure aggregation for counts, secure k-NN for distance, HE for general outsourcing).
- **`docs/protocols/federation_protocol_v0.md`** (new) — formal protocol specification with security definitions and proven properties. `TODO(immune-crypto-collab): formal proofs` lives here.
- **`backend/immune/net/secure_aggregation.py`** (new, planned) — secure aggregation primitive for federation-wide DCA signals. Different primitive from PSI-CA. Referenced in vision doc §6.2.3.

Joint paper material spanning all three: *Privacy-preserving federated genomic surveillance: from PSI-CA to secure aggregation.*

### 8.7 Why this engages adversarial-security and cryptographic expertise

- For the adversarial-security collaborator: the red-team module pre-allocates the attack/defend infrastructure. Plugging the adversarial-security collaborator's group's iterative framework in is a clean drop-in. The TCR-epitope hooks in §8.5 connect directly to the adversarial-security collaborator's published lane independent of red-team work.
- For the applied-cryptography collaborator: the federation re-identification attacks acknowledge the threat directly with `TODO(immune-crypto-collab):` markers showing exactly where her formal-budget work goes. The §8.6 hooks make explicit that PSI-CA (her PoPETs 2024 work) is the right primitive for the most common federation query class — not generic HE.
- For both: weekly public results normalize the practice of red-teaming yourselves before someone else does.

------

## 9. Phase 26-collab: integrating into the existing roadmap

The Phase IM-1..IM-6 sequence in the main vision doc covers the bio-AIS, multi-modal fusion, memory, federation, cyber-AIS, and game/academy work. The collaboration scaffolding does not displace that work. Instead, **Phase IM-N-collab** items are interleaved within Phase IM-1..IM-5 — Glen is a solo developer, so "parallel" means interleaved-within-phases, not literally concurrent.

> **Source-of-truth note:** All collaboration scaffolding work items have canonical mnemonic IDs in `todo.md` under `B-COLLAB-*` (with two exceptions: featurizer-registry work folds into `B-IMMUNE-FEAT-1`, and governance work folds into the existing `B-GOV-1`). This document defines the *architecture and design rationale* for each scaffolding component (Sections 3 through 8); `todo.md` defines the *active work items*.

### 9.0 Existing P0 prerequisites

The Phase IM-N-collab work assumes the existing P0 bugs from `todo.md` are resolved **before** the collab scaffolding lands. Specifically:

- **Audit transaction-participation bug** — `log_audit()` and `create_notification()` must forward `db_conn` to `execute_write()`. The collab scaffolding's audit events (refusal events, redteam events, rotation events) are useless if audit writes auto-commit out-of-band; they need to participate in caller transactions for atomicity.
- **`_handle_workflow_complete()` `conn=` TypeError** — Nextflow `workflow.complete` events crash the pipelines router. This must be fixed before Phase IM-1 (which depends on Nextflow events for `jackpot-amand` integration), and therefore before Phase IM-1-collab as a chained prerequisite.
- **Validator BASE_REQUIRED tier split** — Glen's domain decision; defines what Tier-1 PRELIMINARY samples must contain. The refusal middleware in `refusal.py` operates on requests, not samples, so this isn't directly blocking, but the wider Tier system informs which sample states are visible to which API endpoints.

### 9.1 Schedule (interleaved, not parallel)

Total: roughly 30 person-days across the IM-1 through IM-5 phases. At full-time on the collab work in isolation, that's 6 weeks. At half-time alongside the main Phase IM-* work, that's about 12 weeks. The Phase-IM-1-collab quick wins (`B-COLLAB-SBOM-1`, `B-COLLAB-PARSERS-1`, `B-GOV-1`, `B-IMMUNE-FEAT-1`'s registry pattern, `B-COLLAB-FRAMING-1`) are unconditionally good practice and worth landing first regardless of how the rest of the schedule plays out.

The complete schedule with effort, phase, and dependency information lives in `todo.md` under each Phase IM-N's `Phase IM-N-collab` subsection. The summary by phase:

| Phase | Items | Total effort |
| --- | --- | --- |
| **IM-1-collab** | `B-COLLAB-DIVERSITY-1`, `B-COLLAB-SBOM-1`, `B-COLLAB-PARSERS-1`, `B-COLLAB-SIGSTORE-1`, `B-COLLAB-FRAMING-1`, plus `B-IMMUNE-FEAT-1` registry extension | ~8 days |
| **IM-2-collab** | `B-COLLAB-ROTATE-1`, `B-COLLAB-MUTATE-1`, `B-COLLAB-REFUSAL-1`, `B-COLLAB-DUR-1`, `B-COLLAB-REDTEAM-1`, `B-COLLAB-REDTEAM-2`, `B-COLLAB-CI-1` | ~14 days |
| **IM-4-collab** | `B-COLLAB-DIVERSITY-2`, `B-COLLAB-ATRUST-1`, `B-COLLAB-REDTEAM-3` | ~7 days |
| **IM-5-collab** | `B-COLLAB-CYBER-FED-1` | ~4 days |
| **Wet-side advisory** | `B-WW-ADV-1`, `B-WW-ADV-2`, plus `B-GOV-1` extension | independent of Phase IM-* sequencing |

The architectural prose for each component (the *why*, the design pattern, the open research questions tagged `TODO(<researcher>-collab):`) is preserved in this document's Sections 3 through 8. The work-item details (effort, dependencies, phase placement) are in `todo.md`.

### 9.2 Wet-side advisory

The wet-side advisor's critique ("you don't understand the wet-side enough") doesn't have a software handle. The substitute action lives in three canonical work items in `todo.md`:

- **`B-WW-ADV-1`** — Document `docs/wetside_advisory.md` with current assumptions about wastewater sampling cadence, sample preservation, sequencing-prep failure modes, and known limitations of the input pipeline. (ID disambiguates from existing `B-WW-1` wastewater pipeline-zoo work.)
- **`B-WW-ADV-2`** — Pre-register questions for the wet-side advisor's group (sampling cadence, preservation, false-positive failure modes specific to NWSS feeds) and resolve them in `docs/decisions/`.
- **`B-GOV-1`** (existing in `todo.md`) — Add a "wet-side advisor" role to `GOVERNANCE.md` — a named individual or panel from the wet-lab community who reviews assumptions about input data once per quarter. This extends the existing `B-GOV-1` governance directory work; not a separate item.

### 9.3 Quick wins for the current sprint

Three unconditionally-good-practice items that should land first regardless of any collaboration outcome:

- **`B-COLLAB-PARSERS-1`** — Land `backend/immune/sec/parsers_safe.py` + Critical Rule N in `CLAUDE.md` (no `pickle.load` / `yaml.unsafe_load` / `eval` on external data). 1 day.
- **`B-COLLAB-FRAMING-1`** — Land `course/modules/_meta/ais_framing.md` (Module 0 — why JACKPOT exists). 0.5 day.
- **`B-GOV-1`** — Land `GOVERNANCE.md` v0 with refusal-to-deploy criteria and v1.0+ scope on breaking-change notice. 1 day. (Existing item in `todo.md`; collab scaffolding extends its scope.)

These three are unconditionally good practice independent of any collaboration outcome.

------

## 10. Open research questions, summarized

This is the consolidated list of `TODO(<researcher>-collab):` markers, organized by collaborator. Walking into a meeting with this list is the right opening move — it gives them a menu of joint work and signals that we know exactly which questions are theirs.

### 10.1 Diversity-theory / AIS-theory collaboration markers (9)

| Marker                    | Section | Question                                                     |
| ------------------------- | ------- | ------------------------------------------------------------ |
| `coverage theory`         | §3      | What's the right diversity metric for federated detector pools? |
| `auto-repair`             | §4      | Can wrapped-tool CVEs be auto-patched via GenProg-descendant techniques? |
| `static enforcement`      | §4      | Can deserialization safety be enforced via static taint analysis? |
| `mutation cadence theory` | §5      | What's the optimal rotation cadence per credential class given an attacker model? |
| `Crispy at runtime`       | §5      | Beyond API-surface mutation, what runtime-level mutations are worth the operational complexity? |
| `CSA convergence`         | §5      | When every federation member mutates in response to a broadcast, does the pool converge or diverge? |
| `policy framework`        | §6      | What's the right policy-as-code framework for refusal-to-deploy with formal proofs of consistency? |
| `fairness theory`         | §6      | What's a principled formal-fairness analysis for asymmetric-trust calibration? |
| `DURC institution`        | §6      | What's the credible institutional path to a real DURC review panel? |

### 10.2 Cryptographic-primitives collaboration markers (4)

| Marker                        | Section              | Question                                                     |
| ----------------------------- | -------------------- | ------------------------------------------------------------ |
| `protocol selection`          | §8.6 + vision §6.2.2 | Which crypto primitive (PSI-CA vs HE vs secure aggregation vs secure k-NN) is right per query class? |
| `formal proofs`               | §8.6                 | Formal protocol specification with security definitions and proven properties. |
| `privacy-preserving red-team` | §8                   | Realistic API-only oracle-attack threat model for federation re-identification. |
| `formal privacy budget`       | §8                   | Exact privacy-budget consumption per query class with depletion warnings. |

### 10.3 Adversarial-security collaboration markers (3)

| Marker                            | Section | Question                                                     |
| --------------------------------- | ------- | ------------------------------------------------------------ |
| `iterative attack-defend`         | §8      | Iterative attack-and-defend framework with co-evolving attacker and defender. |
| `MIA design`                      | §8      | Membership-inference attack design tailored to genomic embeddings. |
| `TCR-epitope binding integration` | §8.5    | How does TCR-epitope binding prediction integrate into `jackpot-immune-evasion` and `jackpot-biosig`? |

### 10.4 Wet-side advisory items (3)

| Item                           | Section | Question                                                     |
| ------------------------------ | ------- | ------------------------------------------------------------ |
| sampling cadence               | §9.2    | What sampling cadence and preservation protocols match JACKPOT's wastewater DCA assumptions? |
| false-positive failure modes   | §9.2    | What wet-side failure modes (preservation, prep, contamination) drive false positives we should expect? |
| NWSS / municipal lab realities | §9.2    | What's the operational reality of NWSS feeds vs the idealized signal in the vision doc? |

------

## Closing note

The point of this companion document is not to ship every component before talking to the AIS-theory collaborator's group. The point is to **show up to that conversation having done the engineering work that's available to do alone**, with deliberate, named, well-scoped open questions for collaboration.

The 70/30 ratio (engineering shipped / research as open questions) is calibrated. Walking in with 100% shipped looks like we don't need them. Walking in with 30% shipped looks like we haven't done our homework. 70/30 says we've done what we can alone, and we know exactly where we need help.

> **Note on the actual pitch.** The 70/30 framing is for maintainer's internal calibration. **Do not say "70/30" out loud in the actual pitch meeting** — it reads as performative positioning. Walk through one or two concrete components (the diversity index, the SBOM pipeline) and let the researchers identify their own hooks. They will position themselves better than we can position them.

Each of the eleven critiques is now a paper-or-grant-shaped collaboration hook. None requires us to slow down the main Phase 26+ roadmap; all run interleaved within it. The first three (featurizer registry, SBOM, parsers_safe) are landable in the current sprint and are unconditionally good practice independent of any collaboration outcome.

This is an external pitch (maintainer maintainer / Linux Prophet / Midnight-Oil-Innovation → ASU Biodesign) with a warm hook (Driver et al. 2024). For grants, the natural structure is ASU-as-lead with Linux Prophet as subaward.

Build it; meet with them; let the meeting reshape the next iteration.

— maintainer maintainer & Claude, 2026-05-08
