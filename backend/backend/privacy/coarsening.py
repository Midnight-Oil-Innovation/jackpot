"""Output-boundary generalization (k-anonymity-style coarsening).

Wraps and consolidates the existing coarsening helpers used at API output
boundaries (search responses, federation push payloads, export artifacts).
Track 1 - call-through to existing prod code; Track 2 hook seam for
synthetic-substitute padding when result sets fall below k.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.privacy._ais_hooks import AISPrivacyHooks, NullAISPrivacyHooks


@dataclass
class CoarseningPolicy:
    """Per-tenant coarsening policy.

    Defaults match the JACKPOT v1 generalization defaults. Per-tenant overrides
    are read from organization settings at request time and passed in here.
    """

    age_bin_years: int = 5
    location_granularity: str = "state"  # "city" | "county" | "state" | "country"
    date_granularity: str = "month"  # "day" | "week" | "month" | "quarter"
    k_threshold: int = 5
    use_synthetic_substitute: bool = False


class Coarsener:
    """Apply k-anonymity-style coarsening to records at output boundaries.

    Track 1 - wraps and delegates to existing coarsening helpers; integrates
    optional synthetic_substitute hook when policy.use_synthetic_substitute
    is enabled and the result set would fall below policy.k_threshold.

    The hook seam:
      - When the result set is smaller than k_threshold and the policy
        requests synthetic padding, hooks.synthetic_substitute() is called
        to pad with synthetic records preserving distributional properties.
      - Track 1 default (NullAISPrivacyHooks): synthetic_substitute is
        identity, so the result set passes through unmodified.
    """

    def __init__(
        self,
        policy: CoarseningPolicy | None = None,
        hooks: AISPrivacyHooks | None = None,
    ) -> None:
        self.policy = policy or CoarseningPolicy()
        self.hooks: AISPrivacyHooks = hooks or NullAISPrivacyHooks()

    def coarsen_age(self, age_years: int | None) -> str | None:
        """Bin a host age into the configured age range.

        TODO(privacy-scaffold): align signature with existing age coarsener
        in backend.helpers.coarsening (or wherever host_age_range lives).
        Once aligned, this method delegates rather than reimplementing.
        """
        if age_years is None:
            return None
        bin_width = self.policy.age_bin_years
        lo = (age_years // bin_width) * bin_width
        hi = lo + bin_width - 1
        return f"{lo}-{hi}"

    def coarsen_location(
        self,
        country: str | None,
        state: str | None = None,
        county: str | None = None,
        city: str | None = None,
    ) -> dict[str, str | None]:
        """Generalize location fields to the configured granularity.

        TODO(privacy-scaffold): align with existing location coarsener.
        """
        granularity = self.policy.location_granularity
        out: dict[str, str | None] = {"country": country}
        if granularity in ("city", "county", "state"):
            out["state"] = state
        if granularity in ("city", "county"):
            out["county"] = county
        if granularity == "city":
            out["city"] = city
        return out

    def coarsen_date(self, date_str: str | None) -> str | None:
        """Truncate an ISO-8601 date (YYYY-MM-DD) to configured granularity."""
        if not date_str:
            return None
        granularity = self.policy.date_granularity
        if granularity == "day":
            return date_str
        if granularity == "week":
            # ISO week bucket (YYYY-Www) — finer than month. Falls back to
            # month precision if the input isn't a parseable date.
            try:
                from datetime import date as _date

                from backend.epiweek import compute_epiweeks

                ew = compute_epiweeks(_date.fromisoformat(date_str[:10]))
                return f"{ew['iso_year']}-W{ew['iso_week']:02d}"
            except ValueError:
                return date_str[:7]
        if granularity == "month":
            return date_str[:7]  # YYYY-MM
        if granularity == "quarter":
            year, month = date_str[:4], int(date_str[5:7])
            q = (month - 1) // 3 + 1
            return f"{year}-Q{q}"
        return date_str

    def apply_to_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Apply all coarsening rules to a single sample record."""
        out = dict(record)
        if "host_age_years" in out:
            out["host_age_range"] = self.coarsen_age(out.pop("host_age_years"))
        location = self.coarsen_location(
            country=out.get("country"),
            state=out.get("state"),
            county=out.get("county"),
            city=out.get("city"),
        )
        out.update(location)
        if "collection_date" in out:
            out["collection_date"] = self.coarsen_date(out["collection_date"])
        return out

    def apply_to_resultset(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Apply coarsening to a result set; pad with synthetic if below k.

        If the resulting set has fewer than self.policy.k_threshold rows and
        self.policy.use_synthetic_substitute is True, the synthetic_substitute
        hook is invoked. Track 1 default: returns records unchanged because
        NullAISPrivacyHooks.synthetic_substitute is identity.
        """
        coarsened = [self.apply_to_record(r) for r in records]
        if self.policy.use_synthetic_substitute and len(coarsened) < self.policy.k_threshold:
            coarsened = self.hooks.synthetic_substitute(coarsened, fidelity_target=0.8)
        return coarsened
