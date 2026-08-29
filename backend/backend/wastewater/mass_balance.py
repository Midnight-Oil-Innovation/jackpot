# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Plaintext mass-balance computation for wastewater epidemiology.

Implements the wastewater epidemiology mass-balance equation

    MassLoad = (Q1 . C1) - (Q2 . C2)

where Q1 and Q2 are volumetric flow rates at two sampling points in
the same sewershed and C1 and C2 are pathogen or chemical
concentrations measured at the same points. With Q1.C1 the
downstream pair and Q2.C2 the upstream pair, the equation isolates
the mass-load contribution of the sewershed segment lying between
the two samplers (cryptWWDB Use Case 1). The time-aware variant
(Use Case 2) compares the per-sample mass load at two timestamps to
expose temporal change in the segment's contribution.

This module is the Tier 1 plaintext reference implementation. The
Track 2 homomorphic-encryption backend (B-IMMUNE-HE-1, Phase IM-4)
delegates to the function-level interface defined here so the
encrypted variant stays bit-for-bit faithful to the plaintext one
when evaluated over RLWE-encrypted operands.

``load_inputs_from_db`` resolves ``MassBalanceInputs`` from the
``wastewater_target_concentration`` result table (B-CWB-SCHEMA-2) and
the ``wastewater_upstream_of`` value on ``sample_associations``
(B-CWB-SCHEMA-1), both shipped in the P0b migration
(``c871b28bbdab``). Callers may still assemble ``MassBalanceInputs``
directly when data doesn't come from those tables.

Citation:
    Driver, A., Ahsan, A., Piske, M., Lee, K., Forrest, S.,
    Halden, R.U., Trieu, N.H. (2024). Encrypted data-sharing for
    preserving privacy in wastewater-based epidemiology.
    *Science of the Total Environment*, 940, 173315.
    NSF 2115075.

Non-detect handling follows Hornung & Reed (1990) LOD/2 substitution.
Negative-mass-balance handling follows Bowes et al. 2023b and
Tempe 2023a conventions, switchable via the ``negative_handling``
keyword on the compute functions.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from backend.database import execute_query

logger = logging.getLogger(__name__)


class FlowUnit(StrEnum):
    MGD = "MGD"
    M3_PER_DAY = "m3/day"
    L_PER_DAY = "L/day"
    L_PER_SEC = "L/s"


class ConcentrationUnit(StrEnum):
    NG_PER_L = "ng/L"
    UG_PER_L = "ug/L"
    MG_PER_L = "mg/L"
    COPIES_PER_ML = "copies/mL"
    COPIES_PER_L = "copies/L"


class QualityFlag(StrEnum):
    NON_DETECT_UPSTREAM = "non_detect_upstream"
    NON_DETECT_DOWNSTREAM = "non_detect_downstream"
    BELOW_LOD_UPSTREAM = "below_lod_upstream"
    BELOW_LOD_DOWNSTREAM = "below_lod_downstream"
    NEGATIVE_MASS_BALANCE = "negative_mass_balance"
    MISSING_DATA = "missing_data"
    UNIT_INCOMPATIBLE = "unit_incompatible"


@dataclass(frozen=True)
class FlowRate:
    value: float
    unit: FlowUnit


@dataclass(frozen=True)
class Concentration:
    value: float
    unit: ConcentrationUnit
    lod: float | None = None
    loq: float | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None


@dataclass(frozen=True)
class MassBalanceInputs:
    upstream_flow: FlowRate
    upstream_concentration: Concentration
    downstream_flow: FlowRate
    downstream_concentration: Concentration
    target_pathogen_id: str | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True)
class MassBalanceResult:
    mass_load_value: float
    mass_load_unit: str
    quality_flags: tuple[QualityFlag, ...]
    negative_mass_balance: bool
    error_estimate: float | None = None


# 1 US gallon = 3.785411784 L exactly; 1 MGD = 1e6 gal/day = 3,785,411.784 L/day.
_L_PER_US_GALLON: float = 3.785411784
_L_PER_DAY_FROM_MGD: float = 1_000_000.0 * _L_PER_US_GALLON

_FLOW_TO_L_PER_DAY: dict[FlowUnit, float] = {
    FlowUnit.MGD: _L_PER_DAY_FROM_MGD,
    FlowUnit.M3_PER_DAY: 1_000.0,
    FlowUnit.L_PER_DAY: 1.0,
    FlowUnit.L_PER_SEC: 86_400.0,
}

_MASS_UNITS: frozenset[ConcentrationUnit] = frozenset(
    {
        ConcentrationUnit.NG_PER_L,
        ConcentrationUnit.UG_PER_L,
        ConcentrationUnit.MG_PER_L,
    }
)

_COPIES_UNITS: frozenset[ConcentrationUnit] = frozenset(
    {
        ConcentrationUnit.COPIES_PER_ML,
        ConcentrationUnit.COPIES_PER_L,
    }
)

_MASS_TO_NG_PER_L: dict[ConcentrationUnit, float] = {
    ConcentrationUnit.NG_PER_L: 1.0,
    ConcentrationUnit.UG_PER_L: 1_000.0,
    ConcentrationUnit.MG_PER_L: 1_000_000.0,
}

_COPIES_TO_COPIES_PER_L: dict[ConcentrationUnit, float] = {
    ConcentrationUnit.COPIES_PER_L: 1.0,
    ConcentrationUnit.COPIES_PER_ML: 1_000.0,
}


def to_l_per_day(flow: FlowRate) -> float:
    """Return ``flow`` expressed in L/day, the canonical flow unit."""
    return flow.value * _FLOW_TO_L_PER_DAY[flow.unit]


def to_ng_per_l(conc: Concentration) -> float:
    """Return ``conc`` expressed in ng/L (canonical for chemical mass targets).

    Raises ``ValueError`` if ``conc`` is expressed in copies-based units.
    """
    if conc.unit not in _MASS_UNITS:
        raise ValueError(
            f"Cannot convert {conc.unit.value} to ng/L: concentration is "
            f"expressed in copies-based units. Use to_copies_per_l() instead."
        )
    return conc.value * _MASS_TO_NG_PER_L[conc.unit]


def to_copies_per_l(conc: Concentration) -> float:
    """Return ``conc`` expressed in copies/L (canonical for pathogen targets).

    Raises ``ValueError`` if ``conc`` is expressed in mass-based units.
    """
    if conc.unit not in _COPIES_UNITS:
        raise ValueError(
            f"Cannot convert {conc.unit.value} to copies/L: concentration is "
            f"expressed in mass-based units. Use to_ng_per_l() instead."
        )
    return conc.value * _COPIES_TO_COPIES_PER_L[conc.unit]


NegativeHandling = Literal["zero", "mdl", "raw"]


def _is_mass_unit(unit: ConcentrationUnit) -> bool:
    return unit in _MASS_UNITS


def _canonical_factor(unit: ConcentrationUnit) -> float:
    if unit in _MASS_UNITS:
        return _MASS_TO_NG_PER_L[unit]
    return _COPIES_TO_COPIES_PER_L[unit]


def _append_unique(flags: list[QualityFlag], flag: QualityFlag) -> None:
    if flag not in flags:
        flags.append(flag)


def _resolve_concentration(
    conc: Concentration,
    *,
    is_mass: bool,
    upstream: bool,
    flags: list[QualityFlag],
) -> float:
    """Convert ``conc`` to canonical units, applying non-detect substitution.

    Returns the canonical concentration (ng/L for mass targets, copies/L
    for pathogen targets). Appends quality flags to ``flags`` in-place when
    non-detect (value <= 0) or below-LOD (0 < value < lod) substitution
    fires. Per Hornung & Reed 1990 the substitution value is LOD/2.
    """
    canonical = to_ng_per_l(conc) if is_mass else to_copies_per_l(conc)
    lod_canonical: float | None = (
        conc.lod * _canonical_factor(conc.unit) if conc.lod is not None else None
    )

    # <= 0 rather than == 0: a measured concentration is physically
    # non-negative, so treat exact zero and any (erroneous or
    # baseline-subtracted) non-positive value as a non-detect instead of
    # letting a brittle float-equality check pass a negative through.
    if conc.value <= 0.0:
        flags.append(
            QualityFlag.NON_DETECT_UPSTREAM if upstream else QualityFlag.NON_DETECT_DOWNSTREAM
        )
        if lod_canonical is not None:
            return lod_canonical / 2.0
        _append_unique(flags, QualityFlag.MISSING_DATA)
        return 0.0

    if lod_canonical is not None and canonical < lod_canonical:
        flags.append(
            QualityFlag.BELOW_LOD_UPSTREAM if upstream else QualityFlag.BELOW_LOD_DOWNSTREAM
        )
        return lod_canonical / 2.0

    return canonical


def _mdl_equivalent_load(
    inputs: MassBalanceInputs,
    *,
    flags: list[QualityFlag],
) -> float:
    """Return the downstream LOD/2 equivalent load (Tempe 2023a convention).

    Falls back to zero with a MISSING_DATA flag when the downstream
    concentration has no LOD attached.
    """
    down = inputs.downstream_concentration
    if down.lod is None:
        _append_unique(flags, QualityFlag.MISSING_DATA)
        return 0.0
    lod_canonical = down.lod * _canonical_factor(down.unit)
    return to_l_per_day(inputs.downstream_flow) * (lod_canonical / 2.0)


def _apply_negative_handling(
    raw: float,
    *,
    negative_handling: str,
    inputs: MassBalanceInputs,
    flags: list[QualityFlag],
) -> float:
    if negative_handling == "zero":
        return 0.0
    if negative_handling == "mdl":
        return _mdl_equivalent_load(inputs, flags=flags)
    if negative_handling == "raw":
        return raw
    raise ValueError(
        f"Unknown negative_handling={negative_handling!r}; expected one of 'zero', 'mdl', 'raw'."
    )


def compute_mass_load(
    inputs: MassBalanceInputs,
    *,
    negative_handling: NegativeHandling = "zero",
) -> MassBalanceResult:
    """Compute MassLoad = (Q_down . C_down) - (Q_up . C_up). cryptWWDB Use Case 1.

    Positive values indicate net addition of the target between the
    upstream and downstream samplers (the typical signal for illicit
    inputs to the segment per Driver et al. 2024). Negative values are
    routed through ``negative_handling`` per Bowes et al. 2023b / Tempe
    2023a conventions.

    Parameters
    ----------
    inputs:
        Upstream + downstream flow rates and concentrations.
    negative_handling:
        ``"zero"`` (default) clamps a negative result to zero with the
        NEGATIVE_MASS_BALANCE flag set; ``"mdl"`` substitutes the
        downstream LOD/2 equivalent load; ``"raw"`` preserves the raw
        negative value.

    Raises
    ------
    ValueError
        If upstream and downstream concentrations are not both mass-based
        or both copies-based, or if ``negative_handling`` is not one of
        the three supported strings.
    """
    flags: list[QualityFlag] = []

    up_unit = inputs.upstream_concentration.unit
    down_unit = inputs.downstream_concentration.unit
    upstream_is_mass = _is_mass_unit(up_unit)
    downstream_is_mass = _is_mass_unit(down_unit)
    if upstream_is_mass != downstream_is_mass:
        flags.append(QualityFlag.UNIT_INCOMPATIBLE)
        raise ValueError(
            "Upstream and downstream concentrations must both be mass-based "
            f"or both copies-based; got {up_unit.value} and {down_unit.value}."
        )
    is_mass = upstream_is_mass
    mass_load_unit = "ng/day" if is_mass else "copies/day"

    q_up = to_l_per_day(inputs.upstream_flow)
    q_down = to_l_per_day(inputs.downstream_flow)

    if q_up <= 0.0 or q_down <= 0.0:
        _append_unique(flags, QualityFlag.MISSING_DATA)
        return MassBalanceResult(
            mass_load_value=0.0,
            mass_load_unit=mass_load_unit,
            quality_flags=tuple(flags),
            negative_mass_balance=False,
        )

    c_up = _resolve_concentration(
        inputs.upstream_concentration, is_mass=is_mass, upstream=True, flags=flags
    )
    c_down = _resolve_concentration(
        inputs.downstream_concentration, is_mass=is_mass, upstream=False, flags=flags
    )

    raw = q_down * c_down - q_up * c_up
    negative = raw < 0.0

    if negative:
        flags.append(QualityFlag.NEGATIVE_MASS_BALANCE)
        reported = _apply_negative_handling(
            raw,
            negative_handling=negative_handling,
            inputs=inputs,
            flags=flags,
        )
    else:
        reported = raw

    return MassBalanceResult(
        mass_load_value=reported,
        mass_load_unit=mass_load_unit,
        quality_flags=tuple(flags),
        negative_mass_balance=negative,
    )


def compute_time_aware_mass_load(
    t1: MassBalanceInputs,
    t2: MassBalanceInputs,
    *,
    negative_handling: NegativeHandling = "zero",
) -> MassBalanceResult:
    """Compute the change in net mass load between two timestamps. Use Case 2.

    Implements the temporal-equality variant from Driver et al. 2024:
    the two ``MassBalanceInputs`` describe the same sampler pair at two
    different timestamps. Returns ``load(t2) - load(t1)``, the per-sample
    delta, with quality flags from both endpoints merged. The
    ``negative_handling`` keyword controls reporting when the delta is
    negative (i.e., when the segment's contribution shrank).
    """
    r1 = compute_mass_load(t1, negative_handling="raw")
    r2 = compute_mass_load(t2, negative_handling="raw")

    if r1.mass_load_unit != r2.mass_load_unit:
        raise ValueError(
            f"Time-aware mass load requires matching units at both "
            f"timestamps; got {r1.mass_load_unit} and {r2.mass_load_unit}."
        )

    merged: list[QualityFlag] = []
    for f in (*r1.quality_flags, *r2.quality_flags):
        _append_unique(merged, f)

    raw_delta = r2.mass_load_value - r1.mass_load_value
    negative = raw_delta < 0.0

    if negative:
        _append_unique(merged, QualityFlag.NEGATIVE_MASS_BALANCE)
        reported = _apply_negative_handling(
            raw_delta,
            negative_handling=negative_handling,
            inputs=t2,
            flags=merged,
        )
    else:
        reported = raw_delta

    return MassBalanceResult(
        mass_load_value=reported,
        mass_load_unit=r1.mass_load_unit,
        quality_flags=tuple(merged),
        negative_mass_balance=negative,
    )


def _resolve_upstream_sample_id(sample_id: str, conn: Any) -> str:
    """Return the ``samples.sample_id`` upstream of ``sample_id`` in its sewershed.

    Follows the ``wastewater_upstream_of`` value on ``sample_associations``
    (source = upstream, target = downstream).
    """
    rows = execute_query(
        "SELECT id FROM samples WHERE sample_id = :sample_id",
        {"sample_id": sample_id},
        conn=conn,
    )
    if not rows:
        raise ValueError(f"No samples row found for sample_id={sample_id!r}.")
    downstream_id = rows[0]["id"]

    rows = execute_query(
        """
        SELECT s.sample_id
        FROM sample_associations sa
        JOIN samples s ON s.id = sa.source_sample_id
        WHERE sa.target_sample_id = :downstream_id
          AND sa.association_type = 'wastewater_upstream_of'
        """,
        {"downstream_id": downstream_id},
        conn=conn,
    )
    if not rows:
        raise ValueError(
            f"No wastewater_upstream_of association found for downstream sample_id={sample_id!r}."
        )
    return rows[0]["sample_id"]


def _fetch_latest_concentration_row(
    sample_id: str, target_pathogen_id: str, conn: Any
) -> dict[str, Any]:
    rows = execute_query(
        """
        SELECT * FROM wastewater_target_concentration
        WHERE sample_id = :sample_id AND target = :target
        ORDER BY collection_timestamp DESC NULLS LAST, created_at DESC
        LIMIT 1
        """,
        {"sample_id": sample_id, "target": target_pathogen_id},
        conn=conn,
    )
    if not rows:
        raise ValueError(
            f"No wastewater_target_concentration row found for "
            f"sample_id={sample_id!r}, target={target_pathogen_id!r}."
        )
    return rows[0]


def _row_to_flow(row: dict[str, Any]) -> FlowRate:
    flow = row["flow_rate_mgd"]
    if flow is None:
        raise ValueError(
            f"wastewater_target_concentration row {row['id']} has no "
            "flow_rate_mgd; cannot build FlowRate."
        )
    return FlowRate(value=flow, unit=FlowUnit.MGD)


def _row_to_concentration(row: dict[str, Any]) -> Concentration:
    try:
        unit = ConcentrationUnit(row["concentration_unit"])
    except ValueError as exc:
        raise ValueError(
            f"Unrecognized concentration_unit {row['concentration_unit']!r} on "
            f"wastewater_target_concentration row {row['id']}."
        ) from exc
    # below_lod rows may carry a NULL concentration; 0.0 lets
    # _resolve_concentration's non-detect path apply LOD/2 substitution.
    value = row["concentration"] if row["concentration"] is not None else 0.0
    return Concentration(value=value, unit=unit, lod=row["lod_value"])


def load_inputs_from_db(
    sample_id: str,
    target_pathogen_id: str,
    session: Any,
) -> MassBalanceInputs:
    """Assemble ``MassBalanceInputs`` from the database.

    ``sample_id`` identifies the downstream sample. The upstream sample is
    resolved via the ``wastewater_upstream_of`` association
    (B-CWB-SCHEMA-1); each side's flow and concentration come from its most
    recent ``wastewater_target_concentration`` row for ``target_pathogen_id``
    (B-CWB-SCHEMA-2). ``session`` is a SQLAlchemy connection/session, passed
    through to ``execute_query`` as ``conn``.
    """
    upstream_sample_id = _resolve_upstream_sample_id(sample_id, session)
    downstream_row = _fetch_latest_concentration_row(sample_id, target_pathogen_id, session)
    upstream_row = _fetch_latest_concentration_row(upstream_sample_id, target_pathogen_id, session)

    return MassBalanceInputs(
        upstream_flow=_row_to_flow(upstream_row),
        upstream_concentration=_row_to_concentration(upstream_row),
        downstream_flow=_row_to_flow(downstream_row),
        downstream_concentration=_row_to_concentration(downstream_row),
        target_pathogen_id=target_pathogen_id,
        timestamp=downstream_row["collection_timestamp"] or downstream_row["created_at"],
    )


# --- QC + trigger-point computations (Driver et al. 2024 Table 2, B-CWB-MB-2) ---


def handle_non_detects(values: list[float | None], lod: float) -> list[float]:
    """Replace non-detect (``None``) entries with ``lod / 2``.

    Hornung & Reed (1990) LOD/2 substitution applied element-wise over a
    plain list; detected values pass through unchanged.
    """
    return [lod / 2.0 if v is None else v for v in values]


def clamp_negative_mb(mb: float) -> float:
    """Clamp a negative mass-balance value to zero, logging a WARNING."""
    if mb < 0.0:
        logger.warning("Negative mass balance %s clamped to 0.0", mb)
        return 0.0
    return mb


def propagate_error(values: list[float], rel_errors: list[float]) -> float:
    """Propagate relative errors in quadrature: sqrt(sum((v*e)**2))."""
    if len(values) != len(rel_errors):
        raise ValueError(
            f"values and rel_errors must have equal length; "
            f"got {len(values)} and {len(rel_errors)}."
        )
    return math.sqrt(sum((v * e) ** 2 for v, e in zip(values, rel_errors, strict=True)))


def rolling_average(values: list[float], window: int) -> list[float]:
    """Positional rolling average over the trailing ``window`` points.

    Positions with fewer than ``window`` prior points (including the
    current one) average whatever prefix is available, so the output has
    the same length as ``values``.
    """
    out: list[float] = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1) : i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def trigger_point(mb: float, population: int, threshold_per_100k: float) -> bool:
    """Return True when the per-100k mass-balance rate meets the threshold."""
    if population <= 0:
        raise ValueError(f"population must be positive; got {population}.")
    return (mb / population) * 100_000 >= threshold_per_100k
