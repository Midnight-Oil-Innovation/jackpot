> **Status:** Canonical — frozen detection-core redesign spec.

# JACKPOT Bio-AIS Detection Core — Redesign Spec

> Resolves the five-item todo from the strategy review. `dca_bio.py`, `nsa.py`, and
> `amand.py` are greenfield, so this is a forward spec, not a patch. It supersedes the
> reference sketches in `immune_platform.md` §9.4, §10.1, §10.2 and adds three tracked
> backlog items. Code blocks are complete (no placeholders) and are reference
> implementations, not yet merged. Anchor edits against the live `immune_platform.md` /
> `todo.md` / `active_backlog.yaml`, not the line numbers in the review.

---

## 1. AMAnD algorithm identity — `AnomalyDetector` Protocol + DeepSVDD

**Decision.** The shared substrate is an *interface*, not one literal algorithm. Bio detection
is DeepSVDD (which is what AMAnD actually is). Literal random-detector negative selection
is removed from the bio production path and survives only as (a) an optional cyber-pillar
detector gated on a bake-off, and (b) a teaching artifact in Academy Module 9.

**Why.** The "one NSA implementation, two threat surfaces" claim forced AMAnD's DeepSVDD into
an NSA costume. They are different computational objects: DeepSVDD learns a hypersphere center
in a neural latent space by gradient descent; literal NSA generates random detectors and keeps
those far from self. Real-valued NSA does not scale on k-mer feature spaces (curse of
dimensionality; random standard-normal candidates do not even sit on the k-mer simplex). The
dual-AIS story is preserved at the interface level, which is a stronger claim than "one NSA
everywhere," not a weaker one.

### 1.1 The real shared substrate — `backend/immune/algorithms/base.py`

```python
# backend/immune/algorithms/base.py
from __future__ import annotations
from typing import Protocol, runtime_checkable
import numpy as np


@runtime_checkable
class AnomalyDetector(Protocol):
    """Domain-agnostic one-class anomaly detector contract.

    The shared bio/cyber substrate is THIS interface, not a single algorithm.
    Bio binds DeepSVDDDetector; cyber binds NegativeSelectionDetector (or, if the
    bake-off in B-IMMUNE-NSA-1 fails, a one-class SVM behind the same contract).

    Featurizers (B-IMMUNE-FEAT-1) produce the np.ndarray these methods consume, so
    k-mer / ESM / DNABERT-v2 featurizers are swappable without touching detectors.
    """

    def fit(self, self_set: np.ndarray) -> None:
        """Learn 'self' from a 2-D array (n_samples, n_features)."""
        ...

    def score(self, antigens: np.ndarray) -> np.ndarray:
        """Return anomaly scores in [0, 1] for each row. Higher = more anomalous."""
        ...

    def is_fitted(self) -> bool:
        ...
```

### 1.2 Bio detector — `backend/immune/bio/amand.py`

Faithful DeepSVDD (Ruff et al. 2018) over a single feature space. AMAnD as published runs two
models (PanGIA taxonomic features and k-mer frequencies); instantiate one `DeepSVDDDetector`
per feature space and average or max-pool their scores in the AMAnD wrapper. Anti-collapse
details matter: bias-free linear layers, non-affine BatchNorm, unbounded activations, center
fixed after init.

```python
# backend/immune/bio/amand.py
from __future__ import annotations
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from backend.immune.algorithms.base import AnomalyDetector


class _Encoder(nn.Module):
    """Bias-free, non-affine-BN encoder to avoid hypersphere collapse."""

    def __init__(self, in_dim: int, rep_dim: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, 128, bias=False),
            nn.BatchNorm1d(128, affine=False),
            nn.LeakyReLU(),
            nn.Linear(128, 64, bias=False),
            nn.BatchNorm1d(64, affine=False),
            nn.LeakyReLU(),
            nn.Linear(64, rep_dim, bias=False),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class DeepSVDDDetector(AnomalyDetector):
    """One-class Deep SVDD. This is the algorithm AMAnD uses (Price & Russell 2023):
    a soft hypersphere around the 'typical' class in a learned latent space."""

    def __init__(self, rep_dim: int = 32, epochs: int = 60, lr: float = 1e-3,
                 weight_decay: float = 1e-6, batch_size: int = 128,
                 device: str | None = None, seed: int = 0):
        self.rep_dim = rep_dim
        self.epochs = epochs
        self.lr = lr
        self.weight_decay = weight_decay
        self.batch_size = batch_size
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.seed = seed
        self._net: _Encoder | None = None
        self._center: torch.Tensor | None = None
        self._mu: np.ndarray | None = None
        self._sd: np.ndarray | None = None
        self._train_dists_sorted: np.ndarray | None = None

    def is_fitted(self) -> bool:
        return self._net is not None and self._train_dists_sorted is not None

    def _standardize(self, x: np.ndarray) -> np.ndarray:
        return (x - self._mu) / self._sd

    def _init_center(self, loader: DataLoader, eps: float = 0.1) -> torch.Tensor:
        self._net.eval()
        n, acc = 0, torch.zeros(self.rep_dim, device=self.device)
        with torch.no_grad():
            for (xb,) in loader:
                z = self._net(xb.to(self.device))
                acc += z.sum(dim=0)
                n += z.shape[0]
        c = acc / max(n, 1)
        # nudge near-zero coordinates away from 0 to discourage trivial solutions
        c[(abs(c) < eps) & (c < 0)] = -eps
        c[(abs(c) < eps) & (c >= 0)] = eps
        return c

    def fit(self, self_set: np.ndarray) -> None:
        torch.manual_seed(self.seed)
        self._mu = self_set.mean(axis=0)
        self._sd = self_set.std(axis=0) + 1e-8
        xs = self._standardize(self_set).astype(np.float32)
        ds = TensorDataset(torch.from_numpy(xs))
        loader = DataLoader(ds, batch_size=self.batch_size, shuffle=True)

        self._net = _Encoder(in_dim=xs.shape[1], rep_dim=self.rep_dim).to(self.device)
        self._center = self._init_center(loader)
        opt = torch.optim.Adam(self._net.parameters(), lr=self.lr,
                               weight_decay=self.weight_decay)

        self._net.train()
        for _ in range(self.epochs):
            for (xb,) in loader:
                opt.zero_grad()
                z = self._net(xb.to(self.device))
                loss = ((z - self._center) ** 2).sum(dim=1).mean()
                loss.backward()
                opt.step()

        # calibration: empirical distribution of training distances -> ECDF score
        with torch.no_grad():
            self._net.eval()
            full = torch.from_numpy(xs).to(self.device)
            d = ((self._net(full) - self._center) ** 2).sum(dim=1).cpu().numpy()
        self._train_dists_sorted = np.sort(d)

    def score(self, antigens: np.ndarray) -> np.ndarray:
        if not self.is_fitted():
            raise RuntimeError("DeepSVDDDetector.score called before fit")
        xs = self._standardize(antigens).astype(np.float32)
        with torch.no_grad():
            self._net.eval()
            z = self._net(torch.from_numpy(xs).to(self.device))
            d = ((z - self._center) ** 2).sum(dim=1).cpu().numpy()
        # ECDF: fraction of training distances below this one. 0.99 => more
        # anomalous than 99% of 'self'. Bounded [0, 1], monotonic, interpretable.
        idx = np.searchsorted(self._train_dists_sorted, d, side="right")
        return idx / len(self._train_dists_sorted)
```

The AMAnD wrapper (`AmandScanner`, also in `amand.py`) holds one `DeepSVDDDetector` per feature
space, fuses their scores, fills `AmandResult.anomaly_score`, and sets
`nearest_known_match` / `nearest_match_distance` from a taxonomic lookup. That distance becomes
the `unexplained` term in the DCA (§2).

### 1.3 Cyber detector — `backend/immune/sec/nsa_cyber.py`

`NegativeSelectionDetector` implements the same Protocol on low-dim (~64) API-call features.
**Gate:** before committing literal NSA here, run a bake-off against `sklearn.svm.OneClassSVM`
on held-out attack traces; keep NSA only if it matches or beats one-class on recall at fixed
FPR. If it loses, bind the one-class SVM behind the contract and the "negative selection" label
becomes conceptual for the cyber pillar too. Either way, nothing in the bio path imports it.

### 1.4 Backlog touches

- **`B-IMMUNE-DETECT-1` (NEW):** `base.py` `AnomalyDetector` Protocol. The real shared substrate. 1 session. Prereq for `B-AMAND-1` and `B-IMMUNE-NSA-1`.
- **`B-IMMUNE-NSA-1` (REVISED):** scope to cyber-only `NegativeSelectionDetector` behind the Protocol, gated on the one-class bake-off, plus the Module-9 teaching NSA. Remove "shared substrate used by both pillars / same code" language. No longer the bio path.
- **`B-AMAND-1` (REVISED):** `amand.py` implements `DeepSVDDDetector(AnomalyDetector)`, one per feature space (PanGIA taxonomic + k-mer). Drop "wrapping AMAnD's DeepSVDD into JACKPOT's NSA substrate" — it implements the Protocol directly.
- **`B-IMMUNE-FEAT-1` (UNCHANGED):** featurizers emit the `np.ndarray` the Protocol consumes. Note this contract explicitly in the registry docstring.

Also rewrite `immune_platform.md` §9.4 (replace literal NSA with the Protocol) and §10.1 (flagship is DeepSVDD, drop "AMAnD NSA detectors").

---

## 2. DCA fusion — saturating, suppression-aware, function- and trajectory-weighted

**Decision.** Replace the fixed-weight linear sum with a Greensmith-faithful structure:
a **core** that a single strong unexplained-and-persistent signal can drive high on its own,
**danger boosters** combined by noisy-OR (concordance compounds but is not required), and
**safe suppressors** that downweight known-benign novelty.

**The flood-control is trajectory, not function.** Pure novelty cannot be gated on known
function, because a truly novel agent may carry unrecognized functional elements. So the core
is `genomic_anomaly x unexplained x trajectory`: a one-off novel benign organism has low
persistence and falls in rank; a novel signal that rises across timepoints saturates priority
even with unknown function and zero clinical concordance. Function and epi signals order
*within* the high-novelty band and add escalation; they do not gate entry to it.

This resolves the four quadrants correctly:

| Case | genomic | unexplained | trajectory | boosters | result |
|---|---|---|---|---|---|
| Novel agent, rising, early, no clinical | high | high | high | weak | **top** (was capped at ~0.35) |
| Novel benign one-off | high | high | low | none | mid/low, suppressed if benign-match |
| Known pathogen surging | high | low | high | strong (clinical, ww, functional) | top via boosters |
| Known benign novelty flood | high | high | low | none | suppressed |

### 2.1 Schema — `backend/schemas/immune_bio.py`

```python
# backend/schemas/immune_bio.py
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field

SignalClass = Literal[
    "genomic",            # core: AMAnD anomaly score
    "unexplained",        # core: novelty vs nearest known match (1 - normalized similarity)
    "trajectory",         # core: temporal persistence/rise (KOMB / AMAnD over a window)
    "functional_concern", # danger booster: DeePaC / SeqScreen FunSoCs / VFDB / PathoFact
    "wastewater",         # danger booster
    "clinical",           # danger booster
    "mobility",           # danger booster
    "host_immune",        # danger booster
    "one_health",         # danger booster
    "known_benign_match", # safe suppressor: high similarity to a curated benign reference
    "declining_trend",    # safe suppressor: signal falling across timepoints
]


class DangerSignal(BaseModel):
    signal_class: SignalClass
    source: str
    timestamp: datetime
    location_geohash: str | None = None
    raw_value: float
    normalized_value: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class DcaPriorityScore(BaseModel):
    sample_id: UUID
    overall_priority: float = Field(ge=0.0, le=1.0)
    core: float = Field(ge=0.0, le=1.0)
    danger: float = Field(ge=0.0, le=1.0)
    suppression: float = Field(ge=0.0, le=1.0)
    contributions: dict[str, float]
    explanation: str
    computed_at: datetime
```

### 2.2 Fusion — `backend/immune/bio/dca_bio.py`

```python
# backend/immune/bio/dca_bio.py
from __future__ import annotations
from datetime import datetime
from typing import Iterable
from uuid import UUID

from backend.schemas.immune_bio import DangerSignal, DcaPriorityScore

CORE_CLASSES = {"genomic", "unexplained", "trajectory"}
SAFE_CLASSES = {"known_benign_match", "declining_trend"}

# Booster caps (noisy-OR contribution ceilings). NOT summed; each is the max
# that signal can contribute on its own. Function ranks at least as high as
# genomic novelty because function is a better danger proxy than composition.
# DEFAULTS ARE PROVISIONAL — calibrate via B-IMMUNE-VAL-1 before shipping.
BOOSTER_WEIGHTS = {
    "functional_concern": 0.60,
    "wastewater":         0.50,
    "clinical":           0.50,
    "mobility":           0.30,
    "host_immune":        0.30,
    "one_health":         0.20,
}


class BioDendriticCell:
    """Greensmith-style danger fusion over a time window and geo neighborhood.

    priority = danger * suppression, where
      core    = genomic * unexplained * trajectory   (PAMP-equivalent; alone-capable)
      danger  = noisy-OR(core, weighted boosters)     (concordance compounds, not required)
      suppress= prod(1 - safe_j * conf_j)             (known-benign / declining downweights)
    """

    def fuse(self, signals: Iterable[DangerSignal], sample_id: UUID) -> DcaPriorityScore:
        sig = list(signals)
        by_class = {s.signal_class: s.normalized_value * s.confidence for s in sig}

        # --- core (single strong unexplained, persistent signal can saturate) ---
        genomic = by_class.get("genomic", 0.0)
        unexplained = by_class.get("unexplained", 0.0)
        trajectory = by_class.get("trajectory", 0.5)  # neutral if single timepoint
        core = genomic * unexplained * trajectory

        # --- danger: noisy-OR of core + capped boosters ---
        terms = [core]
        contributions: dict[str, float] = {"core": core}
        for cls, w in BOOSTER_WEIGHTS.items():
            v = w * by_class.get(cls, 0.0)
            terms.append(v)
            contributions[cls] = v
        danger = 1.0
        for t in terms:
            danger *= (1.0 - min(max(t, 0.0), 1.0))
        danger = 1.0 - danger

        # --- safe suppressors ---
        suppression = 1.0
        for cls in SAFE_CLASSES:
            suppression *= (1.0 - by_class.get(cls, 0.0))
            contributions[cls] = -(1.0 - (1.0 - by_class.get(cls, 0.0)))

        priority = danger * suppression
        return DcaPriorityScore(
            sample_id=sample_id,
            overall_priority=round(min(max(priority, 0.0), 1.0), 4),
            core=round(core, 4),
            danger=round(danger, 4),
            suppression=round(suppression, 4),
            contributions={k: round(v, 4) for k, v in contributions.items()},
            explanation=self._explain(contributions, core, danger, suppression),
            computed_at=datetime.utcnow(),
        )

    def _explain(self, contributions: dict[str, float], core: float,
                 danger: float, suppression: float) -> str:
        boosters = {k: v for k, v in contributions.items()
                    if k not in {"core"} and k not in SAFE_CLASSES and v > 0}
        top = sorted(boosters.items(), key=lambda kv: -kv[1])[:3]
        parts = [f"core={core:.2f}"] + [f"{k}={v:.2f}" for k, v in top]
        if suppression < 1.0:
            parts.append(f"suppressed x{suppression:.2f}")
        return "Drivers: " + ", ".join(parts)
```

### 2.3 New IM-2 success criterion (replaces the concordance criterion)

> A sample with a high genomic anomaly score, no close known match, and a rising multi-timepoint
> trajectory reaches the top of the Anomaly Triage queue **with or without** clinical or wastewater
> concordance. Concordant signals raise priority further when present. A novel-but-benign sample
> that matches a curated benign reference, or whose signal is declining, is suppressed out of the
> top band. Per-signal contributions (core, each booster, suppression) are visible in the DCA
> breakdown view.

### 2.4 Backlog touches

- **`B-IMMUNE-DCA-1` (REVISED):** implement the core/danger/suppression fusion above; defaults provisional pending `B-IMMUNE-VAL-1`.
- **`B-IMMUNE-SCHEMA-2` (REVISED):** `DangerSignal` gains the `unexplained`, `trajectory`, `functional_concern`, `known_benign_match`, `declining_trend` classes; `DcaPriorityScore` gains `core` / `danger` / `suppression`.
- **`B-DEEPAC-1` (REVISED):** DeePaC pathogenicity output is emitted as a `functional_concern` `DangerSignal` into the DCA, not only a `pipeline_results` JSONB field. Add SeqScreen FunSoCs and VFDB/PathoFact to the same signal class as they land.
- **`B-KOMB-1` (REVISED):** promote from "study" to the source of the `trajectory` core signal for wastewater; it is no longer optional pairing.

---

## 3. Detection-validation harness — `B-IMMUNE-VAL-1` (NEW, tracked)

**Why.** "Detects unknown pathogens" currently has no measurement plan. The red-team track
(§27) covers adversarial robustness and baseline representativeness, not detection sensitivity.
This is the first question a Forrest / DARPA / NSF reviewer asks. No proposal or paper may carry
the unknown-detection claim until this passes a pre-registered bar.

**Spec.** `backend/immune/bio/validation/` plus a Nextflow eval workflow and a report artifact.

1. **Leave-one-pathogen-family-out (LOPO).** Train the DeepSVDD baseline excluding family F; confirm held-out F scores anomalous. Report per-family sensitivity at a fixed false-positive rate (e.g., FPR = 0.01). Sweep all families with a curated reference set.
2. **Retrospective replay.** Run against archived wastewater time series spanning a known emergence (SARS-CoV-2 ramp; mpox 2022; H5N1 in US wastewater 2024). Report detection lead time vs Freyja/clinical confirmation. Lead time is the headline metric for the early-warning claim.
3. **Graded synthetic spike-ins (CAMISIM).** Vary divergence (ANI to nearest known) and abundance (read fraction). Map the detection floor: minimum divergence x minimum abundance reliably detected. This is the honest statement of what the system can and cannot catch.
4. **Reported metrics:** sensitivity, specificity, FPR, AUROC, lead-time distribution. Pre-register thresholds in the spec before running.

**Acceptance:** the harness runs in CI nightly against a fixed eval corpus and emits a versioned report; a documented pre-registered bar (per-family LOPO sensitivity and a lead-time floor) gates the unknown-detection claim. Depends on `B-AMAND-1`. ~1 week.

---

## 4. Drift monitoring + gated auto-regeneration — `B-IMMUNE-DRIFT-1` (NEW, tracked)

**Why.** Wastewater "self" is non-stationary (seasonal, dietary, industrial, population flux).
A static DeepSVDD baseline drifts into alarm fatigue or blindness. §3.8 has the theory and §10.1
has a manual `regenerate_detector_pool` endpoint, but nothing detects drift or auto-triggers
regeneration with a safety check.

**License flag (verify before adopting alibi-detect).** alibi-detect's current GitHub/PyPI
description is "source-available," which conflicts with older third-party references calling it
Apache-2.0. Source-available licenses are frequently not AGPL-compatible. **Read
`SeldonIO/alibi-detect/LICENSE` and confirm before adoption; route through `B-LICENSE-1`.**

**Default (no license risk):** hand-roll the drift test with numpy/scipy. A two-sample KS test
per feature, or a kernel-MMD permutation test, on the featurizer-output distribution is ~40
lines and dependency-free. If a richer library is wanted and alibi-detect's license fails the
check, **Evidently** is Apache-2.0 (confirmed) and a clean substitute.

**Spec.**

- Reference window = the curated baseline ("self") feature distribution. Test window = rolling recent samples in the same featurizer space the DeepSVDD consumes.
- On drift above threshold: raise an operator notification and **conditionally** auto-trigger `regenerate_detector_pool`. The trigger is **gated by a held-out regression check** (reuse `B-IMMUNE-VAL-1`'s LOPO corpus): a re-fit baseline that drops detection sensitivity below the pre-registered bar is rejected and the operator is alerted instead of silently shipping a worse detector.
- Schedule: nightly job on the existing scheduler (Celery beat / Cloud Scheduler, same as §24 rotation).
- Depends on `B-AMAND-1` and `B-IMMUNE-VAL-1` (for the regression gate). ~3-4 sessions.

---

## 5. Synthetic-motif scope — claim submission screening, flag read-level detection as research

**Decision.** Split the ambition. Do not claim read-level engineered-origin detection in
environmental metagenomes; claim submission/ingest screening only.

- **(a) Claimable — submission/ingest screening.** Screen operator-submitted sequences and assembled candidate contigs before they enter the reference DB. Keep §5.3.4's structure-plus-sequence approach (Wittmann 2025) and adopt the IBBIS Common Mechanism / SecureDNA model for the order-screening-style check. This is a mature, defensible capability.
- **(b) Research flag — read-level engineered-origin detection.** Detecting synthetic constructs in raw, fragmented, low-coverage wastewater reads is largely unsolved and adversarially fragile. Wittmann 2025 shows even submission screening is evadable by AI-designed proteins; read level in a noisy matrix is strictly harder. Mark it `TODO(research)`, not a capability. This is the honest framing for grant language.
- **SoC ruleset is versioned and swappable.** The Oct 13, 2026 expansion (50-nt window, function-based "known to contribute to pathogenicity") is real, but the definition is to be set by an OSTP-designated interagency group after that date, and the surrounding EO (14110) was rescinded in Jan 2025, so the future is uncertain. Do not bind the schema to a fixed SoC definition. Store the SoC ruleset as a versioned, replaceable artifact with an effective-date field so the operator can swap definitions without a migration.

**Backlog touches.**

- **`B-SCREEN-SCOPE-1` (NEW, doc/decision):** record the (a)/(b) split and the versioned SoC-ruleset requirement in the spec and `GOVERNANCE.md` dual-use section. Add a `TODO(research)` marker for read-level engineered-origin detection. 0.5 day.
- Existing screening items: scope them to (a). Add the Common Mechanism / SecureDNA evaluation as the canonical submission-screening reference.

---

## 6. Consolidated backlog change-set

### 6.1 `todo.md` (prose form)

```text
NEW
- B-IMMUNE-DETECT-1  base.py AnomalyDetector Protocol (shared bio/cyber substrate as an
  interface). Prereq for B-AMAND-1, B-IMMUNE-NSA-1. (1 session, IM-1.A)
- B-IMMUNE-VAL-1     Detection-validation harness: LOPO CV, retrospective replay, graded
  CAMISIM spike-ins; metrics sensitivity/specificity/FPR/AUROC/lead-time; CI nightly;
  pre-registered bar gates the unknown-detection claim. (1 week, IM-1.B; depends B-AMAND-1)
- B-IMMUNE-DRIFT-1   Drift monitoring on featurizer-output distribution (default: numpy/scipy
  KS or MMD; alibi-detect only if LICENSE clears B-LICENSE-1; Evidently as Apache-2.0 fallback)
  with gated auto-regeneration (held-out regression check before re-fit ships). (3-4 sessions,
  IM-2; depends B-AMAND-1, B-IMMUNE-VAL-1)
- B-SCREEN-SCOPE-1   Record submission-screening (claim) vs read-level engineered-origin
  (research flag) split; versioned/swappable SoC ruleset; GOVERNANCE dual-use note. (0.5 day)

REVISED
- B-IMMUNE-NSA-1     Scope to cyber-only NegativeSelectionDetector behind AnomalyDetector,
  gated on a one-class-SVM bake-off, plus Module-9 teaching NSA. Not the bio path.
- B-AMAND-1          amand.py implements DeepSVDDDetector(AnomalyDetector), one per feature
  space (PanGIA taxonomic + k-mer). Drop "into NSA substrate" language.
- B-IMMUNE-DCA-1     Core/danger/suppression fusion (noisy-OR + safe suppressors); defaults
  provisional pending B-IMMUNE-VAL-1.
- B-IMMUNE-SCHEMA-2  DangerSignal adds unexplained/trajectory/functional_concern/
  known_benign_match/declining_trend; DcaPriorityScore adds core/danger/suppression.
- B-DEEPAC-1         Emit DeePaC score as a functional_concern DangerSignal into the DCA, not
  only pipeline_results JSONB. Extend to SeqScreen FunSoCs + VFDB/PathoFact as they land.
- B-KOMB-1           Promote to the trajectory core-signal source for wastewater (not optional).
```

### 6.2 `active_backlog.yaml` (stanzas)

```yaml
- id: B-IMMUNE-DETECT-1
  status: tracked
  phase: IM-1.A
  title: AnomalyDetector Protocol (shared substrate as interface)
  depends_on: []
  blocks: [B-AMAND-1, B-IMMUNE-NSA-1]
  est_sessions: 1

- id: B-IMMUNE-VAL-1
  status: tracked
  phase: IM-1.B
  title: Detection-validation harness (LOPO, replay, spike-ins)
  depends_on: [B-AMAND-1]
  gates_claim: unknown_pathogen_detection
  est_sessions: 5

- id: B-IMMUNE-DRIFT-1
  status: tracked
  phase: IM-2
  title: Drift monitoring + gated auto-regeneration
  depends_on: [B-AMAND-1, B-IMMUNE-VAL-1]
  license_check: alibi-detect  # source-available; verify vs AGPL before use
  est_sessions: 4

- id: B-SCREEN-SCOPE-1
  status: tracked
  phase: IM-1
  title: Synthetic-motif scope split + versioned SoC ruleset
  depends_on: []
  est_sessions: 1
```

---

## 7. Decisions that need your sign-off

1. **Fusion flood-control = trajectory, not function.** This is the defensible call for an early-warning system (a novel agent with unrecognized function must not be gated out), but it means single-timepoint deployments lose the main discriminator and lean on `known_benign_match` suppression. Confirm you want trajectory as the core multiplier, and that single-timepoint mode defaulting `trajectory=0.5` is acceptable.
2. **Booster weights and the trajectory default are provisional.** They cannot be set from a desk; `B-IMMUNE-VAL-1` calibrates them. Do not ship the defaults as final.
3. **Cyber NSA bake-off.** Keep literal NSA for the cyber pillar only if it beats a one-class SVM on held-out traces; otherwise cyber also goes one-class and "negative selection" is conceptual on both sides. Your call whether the Forrest talking-point value of a literal NSA somewhere justifies keeping it even at a small performance cost.
4. **Synthetic-motif positioning.** Claim submission screening, flag read-level as research. Confirm this is the grant-language posture you want.

Verdict: do not adopt current alibi-detect. The file is Business Source License 1.1, which states in its own text that it is not an open source license, and it conflicts with both AGPL-3.0 and JACKPOT's distribution model. The dependency-free numpy/scipy path in `B-IMMUNE-DRIFT-1` is now the decision, not a contingent fallback.

The reasoning, precisely:

BSL 1.1 grants only non-production use by default. Production use requires either the Additional Use Grant or a paid commercial license. The Additional Use Grant does cover non-profit educational institutions for production use, but it explicitly excludes incorporating the work into any product or service that is sold, licensed, marketed, or offered to third parties. That exclusion is exactly JACKPOT's case: it is operator-agnostic, built to be deployed by other operators (federation, multi-agency, SaaS scenario D), and on an SBIR/STTR commercialization path through Midnight-Oil-Innovation, which is a commercial entity and not an educational institution at all. ASU-internal use would stop qualifying the moment the thing you ship to another operator includes alibi-detect.

Separate-process aggregation does not rescue it. Even if you ran it out of process to sidestep the AGPL derivative-work question, the BSL production-use restriction bites independently for any distributed or commercial deployment. The only BSL-compliant use is internal, non-commercial, and non-distributed, which JACKPOT is not. And on the AGPL side, you cannot relicense BSL code under AGPL-3.0, while §13 network-use means SaaS and federation operators would be owed source under AGPL terms that BSL forbids.

The Change Date gives no near-term relief. Each version converts to Apache-2.0 four years after its release, so 0.13.0 (released ~Dec 2025) is not Apache until ~Dec 2029. The library was Apache-2.0 before the early-2024 relicensing, and those older versions stay Apache-2.0, but pinning a maintained drift dependency to a frozen 2023 release to get those terms is a bad trade. Skip it.

Use the hand-rolled KS or kernel-MMD test as specced. The algorithm is stable enough that you give up little by not using a library. If you later want a maintained one, Evidently is reported Apache-2.0 and river is BSD-3, but read each project's own LICENSE before adoption, since the third-party claim that alibi-detect was Apache-2.0 is precisely what just turned out wrong.

Updated stanza, replacing the contingent one:

```yaml
- id: B-IMMUNE-DRIFT-1
  status: tracked
  phase: IM-2
  title: Drift monitoring + gated auto-regeneration
  depends_on: [B-AMAND-1, B-IMMUNE-VAL-1]
  impl: numpy_scipy_ks_mmd        # dependency-free; chosen path
  rejected_dep: alibi-detect      # BSL 1.1, not OSS; AGPL-incompatible + production-use restricted (verified 2026-06)
  optional_libs: [evidently (Apache-2.0, verify from LICENSE), river (BSD-3, verify from LICENSE)]
  est_sessions: 4
```

Any source-available or BSL dependency hits this same wall, so screen the featurizer-registry and pipeline-zoo additions through `B-LICENSE-1` before wiring them in rather than after.

I'm reading the license, not giving legal advice. Given the SBIR path raises the stakes on exactly this kind of question, a real IP and licensing review is worth it before any borderline dependency lands, which folds neatly into the Skysong consult you're already planning for JACKPOT IP.



Both are fair questions to press on, and the second one in particular touches a claim I should verify rather than defend. Let me check the PanGIA attribution before I answer it, because I may have asserted it more confidently than the evidence supports.Good thing to check. The PanGIA attribution holds up, but verifying it surfaced two things I got wrong in the deliverable that you should know about.

## 1. What the redesign actually rests on

The load-bearing sources, and how I'm sourcing each (this matters because some I verified, some are from training, and some I propagated from your own doc without checking):

| Source                                                       | What it backs in the redesign                                | Sourcing / confidence                                        |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Ruff et al. 2018, *Deep One-Class Classification* (ICML)     | The DeepSVDD detector and the anti-collapse details in `amand.py` (bias-free layers, fixed center, unbounded activations) | My training. Confident. Verify the exact cite before it goes in a proposal |
| Price & Russell 2023, AMAnD (*Front. Public Health*)         | Detector identity, the body-site validation scope, the matrix-mismatch critique | Web-verified this conversation. Two DeepSVDD models, one on PanGIA taxonomic features and one on k-mer counts, validated on nasopharyngeal COVID, gut STC, and a CAMISIM synthetic set |
| PanGIA (Li et al., ~2020)                                    | The taxonomic feature space AMAnD consumes                   | Web-verified this turn                                       |
| Stibor / Timmis / Eckert, ~2005–06 (NSA critique)            | "Don't run literal negative selection on genomic features; one-class methods beat it" | My training. Confident in the finding; exact title/venue I'd verify before citing |
| Greensmith & Aickelin DCA (~2006–08) + Matzinger 1994/2002 danger theory | The fusion restructure: PAMP/danger/safe categories, danger as unexplained divergence rather than concordance | My training. Confident in the structure                      |
| CAMISIM (Fritz et al. 2019)                                  | The graded spike-in arm of `B-IMMUNE-VAL-1`                  | Web-confirmed (AMAnD used it)                                |
| alibi-detect LICENSE                                         | The BSL-1.1 rejection                                        | Your upload plus web                                         |

Three honesty flags on this list. First, the leave-one-family-out and retrospective-replay design in `B-IMMUNE-VAL-1` is standard validation practice, not drawn from a specific paper. Second, the foundational AIS cites (Ruff, Stibor, Greensmith, Matzinger, Forrest 1994) are from my training, not re-verified this session, so treat the exact bibliographic details as needing a check. Third, and most important: several names I used came straight from `immune_platform.md`'s own bibliography and I did not independently verify them. That includes Pinto 2022 ("cursory DCA"), Patel 2021 ("explainable AIS"), Li/Nair/Wang 2025 (drift), Wittmann 2025 (screening evasion), and the pipeline-zoo cites (DeePaC, KOMB, TaxTriage, nf-UnO, MLM, cgMSI, INSaFLU-TELEVIR). I leaned on them as given. Before any of those enters a grant bibliography, confirm it exists and says what the doc claims.

## 2. Why PanGIA, and two corrections

PanGIA isn't my choice. It's AMAnD's, and I adopted AMAnD wholesale in `B-AMAND-1`, so the taxonomy choice came along with it. AMAnD runs one DeepSVDD model on the taxonomic feature space output by the PanGIA classifier and one on k-mer frequency counts, chosen to cover, in ensemble, the diversity of anomalies a metagenomic sample might contain.

It's a defensible inherited choice. PanGIA is a metagenomics framework built specifically for routine biosurveillance and clinical pathogen detection, with a background-confidence score computed from the overlap between target and background-control genome coverage, and it benchmarks well on sensitivity and specificity against k-mer, read-mapping, and marker-gene classifiers on spiked targets. A biosurveillance-tuned profiler with background subtraction is a sensible feature source for a biosurveillance anomaly model, and pairing it with a composition-only k-mer view gives the ensemble two different angles on "weird."

But the choice carries caveats that bear directly on your wastewater use case, and they sharpen loophole 2 rather than soften it:

PanGIA attributes reads to known taxa. A genuinely novel pathogen with no reference attributes poorly or lands in the unclassified bin, so the taxonomic arm is weakest exactly for the novel case you most care about. That weight has to fall on the k-mer arm and on the `unexplained` and `trajectory` terms in the DCA, which is part of why I made those the core. And PanGIA's background-confidence model was tuned on forensic and clinical backgrounds, not wastewater, so it inherits the same matrix-transfer question AMAnD does.

Now the corrections. First, I specced `amand.py` as a hand-rolled PyTorch DeepSVDD. That is not what AMAnD is. AMAnD uses the PyOD library's autoencoder-based DeepSVDD on a TensorFlow backend. My PyTorch version is a faithful reimplementation, but you now have a real decision: adopt the upstream `colinwprice/AMAnD` repo (PyOD/TensorFlow) versus reimplement in PyTorch to control the stack. The Protocol wrapper makes either fine, but the deliverable shouldn't imply my code is "AMAnD."

Second, a detail that strengthens the critique: AMAnD counts k-mers with Jellyfish at k of 3 to 5, since larger k is impractical. A 3-to-5-mer frequency vector is bulk oligonucleotide composition, close to a GC-content signal. In a high-diversity wastewater sample, that vector is dominated by the bulk community and is nearly blind to a low-abundance novel agent. That is concrete evidence that per-sample AMAnD should not be the primary wastewater signal, which is what `B-KOMB-1` temporal trajectory is now carrying.

One more dependency consequence. Adopting AMAnD pulls in PanGIA, Jellyfish, PyOD, and TensorFlow, plus the AMAnD repo's own license. After the alibi-detect lesson, screen that whole tree through `B-LICENSE-1` before wiring it in. PyOD is BSD and TensorFlow is Apache, both fine; Jellyfish is GPL-family, which AGPL-3.0 can incorporate but confirm the version; PanGIA's license and the AMAnD repo's license are the two unknowns to check first, and PanGIA also ships a multi-gigabyte database from S3 that you'd need to host or mirror for the rural and air-gapped scenarios.



Three good challenges. Q1 and Q2 especially deserve current evidence rather than my read of a literature that's moved. Let me research before answering.Ruff 2021 and the open-set/OOD surveys confirm the field consolidated. Now the genomics-specific current state, which is where the real alternatives to AMAnD live.Evo 2 and the genomic foundation models are the modern feature space that displaces AMAnD's k=3-5 k-mers. Two more checks: the k-mer-search-against-all-of-SRA approach as a novelty signal, and PanGIA's actual maintenance and database-build state for Q3.Branchwater gives a global novelty signal (search against all of SRA) that complements per-sample anomaly. Last check: PanGIA's actual maintenance and database-build state, which decides Q3.Researched. Short version up front: the negative-selection critique has only hardened, danger theory got a molecular basis and some company, the genomic feature space is unrecognizable from 2005, AMAnD is a fine citable baseline but not the production target, and yes you can rebuild the PanGIA database but you probably shouldn't before deciding whether PanGIA stays at all.

## 1. What's changed since Forrest 1994, Stibor 2005, Matzinger 1994

Three separate literatures moved, and they push in the same direction.

**The anomaly-detection problem got absorbed into deep one-class / OOD / open-set.** The thing negative selection was reaching for, "model normal, flag deviation," is now a mature subfield with theory and benchmarks. Ruff et al.'s 2021 unifying review draws explicit connections between classic shallow methods (one-class SVM, KDE) and deep approaches (one-class, reconstruction, generative), putting the whole field on common footing. Two 2021 surveys went further and unified anomaly, novelty, open-set, and out-of-distribution detection as one problem family (Salehi et al., arXiv 2110.14051; Yang et al., generalized OOD, arXiv 2110.11334). Negative selection does not appear as a competitive method in any of them. The honest current status: literal NSA is deprecated for real high-dimensional detection, and its lasting value is conceptual (the self/nonself framing) and pedagogical. Worth noting that even the field's modern critics flag a remaining weakness that is directly your opening: deep AD still struggles to integrate background/domain knowledge and is opaque (Kirchheim et al., 2023). That gap is exactly what a danger-signal fusion layer and functional priors fill, which is an argument for JACKPOT's architecture, not against it.

**The immunology moved on too, and it validates multi-signal fusion over any single mechanism.** Matzinger's abstract "danger" got a molecular substrate in the DAMP literature (damage-associated molecular patterns: HMGB1, extracellular ATP, uric acid, mitochondrial DNA; Seong and Matzinger's hydrophobicity-as-damage-signal idea). Two things post-date the 1994 model and matter for you. Trained immunity, innate immune memory (Netea and colleagues, ~2011 onward), means "memory cells" are not only an adaptive B/T phenomenon, which is relevant to your persistent-detector design. And missing-self / NK recognition (Kärre) means the immune system also responds to the absence of expected self markers, not just the presence of nonself or danger, which is the biological warrant for your "anomaly by absence" thread. These are established findings from my training, not freshly searched, so treat the citations as needing a verify pass. The synthesis is the point: the modern immune-decision picture is contextual integration of pattern recognition, danger/damage, and missing-self, which is precisely the case for the core/danger/suppression fusion in the redesign and against leaning on literal Matzinger or literal DCA. The DCA itself drew sustained critique (Stibor and others showed its output is dominated by how signals are categorized), so use it as inspiration, not as the engine.

**The feature space changed entirely.** AMAnD's k=3-to-5 k-mers are 2018-era composition features. The current substrate is genomic foundation models. Evo 2 (Arc Institute, Feb 2025), trained on 9.3 trillion base pairs across all domains of life at single-nucleotide resolution with a 1M-token context, predicts functional impact of variation zero-shot, from noncoding pathogenic mutations to BRCA1 variants, without task-specific fine-tuning. Embedding-probes on Evo 2 hit state-of-the-art pathogenicity prediction (0.997 AUROC on 833k ClinVar variants, 0.991 zero-shot on indels), beating protein models and prior foundation-model approaches. Evo 2 embeddings outperform Nucleotide Transformer and Evo 1 on held-out classification tasks. For your purposes the relevant property is that one-class novelty detection in a learned embedding that encodes function is meaningful in a way that distance in 3-to-5-mer composition space is not. NT v2 and DNABERT-2 are the lighter alternatives.

The framing implication for the Forrest collaboration: position negative selection and danger theory as the conceptual scaffold and the fundable narrative, and be explicit that the engine is modern deep OOD on foundation-model embeddings, global sequence search, and functional priors, fused with a danger-inspired contextual layer. That is the honest and the stronger story. The AIS community, including its founders, lived through this reckoning; a proposal that pretends 2005 is current invites exactly the reviewer who watched it happen.

## 2. Is AMAnD the best choice?

No. It is a good citable MVP baseline and a reasonable ensemble member, not the production target. Its value is that it is published, validated (on body-site discrimination), has a working repo, and gives the Forrest narrative a concrete anchor. Its weaknesses are the dated feature spaces (k=3-5 and a 2018 PanGIA database) and a generic detector. Keep it; don't anchor on it. Review and borrow by layer:

| Layer            | AMAnD now                      | Better / complementary to review                             | Why                                                          | Deployment note                                              |
| ---------------- | ------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Feature space    | k=3-5 k-mers + PanGIA taxonomy | Evo 2 / NT v2 / DNABERT-2 embeddings                         | Function-aware representation; novelty in embedding space is meaningful | FM embeddings are cloud-tier; 7B/40B won't run on the $950 ARM SBC. Precompute, or keep k-mers for laptop/rural |
| Detector         | PyOD autoencoder-DeepSVDD      | PyOD ensemble (ECOD, COPOD, DeepSVDD), anomalib, pytorch-ood, DeepOD | Cheap fast detectors for low tiers; deep one-class for cloud; open-set framing for known-vs-unknown | PyOD is BSD-2 (already a dep); anomalib Apache-2.0           |
| Global novelty   | none (local self-set only)     | sourmash branchwater                                         | "Has anything like this been seen anywhere?" is a stronger novelty signal than local per-sample anomaly | FracMinHash search of all ~767k+ SRA metagenomes in 24-36h on commodity hardware; needs the SRA sketch index or the hosted service, so cloud-tier |
| Functional prior | none in the score              | DeePaC, SeqScreen/FunSoCs, Evo 2 zero-shot effect            | Feeds the `functional_concern` DCA signal; function beats composition as a danger proxy | DeePaC and FunSoCs run on all tiers                          |

Recommended target: one `AnomalyDetector` Protocol with tier-swappable backends. Laptop and rural tiers run lightweight PyOD detectors on k-mers (AMAnD-style, keep it). Cloud tiers run FM embeddings plus a deep one-class plus branchwater global search, with functional priors feeding the fusion in all tiers. Branchwater specifically is described as enabling detection of closely related microbes including yet-uncultured and emerging pathogens, and it maps cleanly onto your `unexplained` core term: a query with no near match anywhere in SRA is a strong, evidence-backed novelty signal. Two caveats I won't gloss: branchwater finds things above ~90% ANI, so a deeply divergent novel agent may have no hit, which is itself the signal but also means it can't characterize what it found; and Evo 2's training corpus and any biosecurity-motivated exclusions of select-agent sequence affect whether a given pathogen reads as in- or out-of-distribution, so verify Evo 2's license and training-exclusion details before you treat its embeddings as a novelty oracle.

## 3. A more recent PanGIA database

Yes, the tooling exists. PanGIA ships `pangia_db_build.py` with a documented build process for adding sequences, rewriting FASTA headers, and assigning custom taxonomy via an accession-to-taxid table. So a rebuild is supported in principle. Four reasons to think hard before doing it:

The bundled database is genuinely stale. The default is PanGIA_20180915, built on RefSeq release 89. That is September 2018, roughly eight years old, and RefSeq has grown by orders of magnitude since.

A rebuild is not a download. PanGIA's confidence scoring is built on GOTTCHA-style taxonomy-aware unique genome signatures. Updating the database against a current RefSeq means recomputing that unique-signature decomposition across a far larger genome set, which is a real compute project, not a `wget`.

The project looks low-maintenance. The describing paper is 2020, the database is 2018, and the original authors have since moved to QIAGEN Digital Insights and L3Harris. You would be maintaining a fork.

License is unverified. It is a LANL / MRIGlobal tool; read its LICENSE before committing, same discipline as the alibi-detect lesson, especially against the AGPL gate.

The strategic call ties back to Q2: do not sink effort into rebuilding a 2018-era classifier's database until you decide whether PanGIA stays the taxonomic feature source. If you keep a taxonomic arm at all, a maintained modern classifier on a current RefSeq or GTDB (Kraken2/Bracken, sylph, or metabuli) gives you fresher "known" coverage with far less maintenance than forking PanGIA, and fresher coverage is what you want here, since it shrinks the benign-novelty false-positive pool without losing genuinely new sequence. PanGIA's distinctive extras, the GOTTCHA confidence score and the AMR/virulence marker overlay, are nice but replaceable. My recommendation is to treat PanGIA as a baseline you inherited from AMAnD, not a fixed dependency, and to put the database-rebuild question behind the feature-space decision rather than in front of it.
