#!/usr/bin/env python3
"""
Seed demo wastewater samples + Freyja lineage-abundance rows for the
B-WW-1 dashboard.

Inserts ≥3 ``WastewaterSample`` rows (sector='wastewater') across ≥2
dates at one site, each with ≥2 ``wastewater_lineage_abundance`` rows
summing to ~1.0. Idempotent: re-running on an already-seeded DB
inserts nothing.

Usage:
    uv run python3 backend/scripts/seed_wastewater_demo.py
    uv run python3 backend/scripts/seed_wastewater_demo.py --dry-run

Depends on the baseline seed (lab_id=1, project_id=1, owner_id=1 — all
shipped by migration 5adf11b77c19) and on migration acd770bb1753 having
created the wastewater_lineage_abundance table.
"""

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://jackpot:jackpot@localhost:5432/jackpot_db",  # pragma: allowlist secret
)

DEMO_RUN_ID = "ww-demo-run-0001"
DEMO_SITE = "Example WWTP — Downtown"

# Three samples, two collection dates, one site. The first two share a
# date so the chart shows multiple samples per epi-week as well as a
# trajectory across weeks.
SAMPLES: list[dict] = [
    {
        "sample_id": "WW-DEMO-001",
        "date_collected": date(2026, 4, 27),
        "flow_rate_mgd": 12.5,
        "population_served": 145_000,
    },
    {
        "sample_id": "WW-DEMO-002",
        "date_collected": date(2026, 4, 27),
        "flow_rate_mgd": 12.7,
        "population_served": 145_000,
    },
    {
        "sample_id": "WW-DEMO-003",
        "date_collected": date(2026, 5, 4),
        "flow_rate_mgd": 13.1,
        "population_served": 145_000,
    },
    {
        "sample_id": "WW-DEMO-004",
        "date_collected": date(2026, 5, 11),
        "flow_rate_mgd": 12.9,
        "population_served": 145_000,
    },
]

# Per-sample lineage mixtures (sum ≈ 1.0). Trend: JN.1 declining, KP.3
# rising, an "other" residual closing the gap.
LINEAGE_MIXTURES: dict[str, list[tuple[str, float]]] = {
    "WW-DEMO-001": [("JN.1", 0.62), ("KP.3", 0.21), ("XEC", 0.10), ("other", 0.07)],
    "WW-DEMO-002": [("JN.1", 0.58), ("KP.3", 0.24), ("XEC", 0.11), ("other", 0.07)],
    "WW-DEMO-003": [("JN.1", 0.41), ("KP.3", 0.38), ("XEC", 0.14), ("other", 0.07)],
    "WW-DEMO-004": [("JN.1", 0.28), ("KP.3", 0.52), ("XEC", 0.13), ("other", 0.07)],
}


def _baseline_present(conn) -> bool:
    """The baseline migration seeds lab_id=1, project=1, owner=1."""
    row = conn.execute(
        text(
            "SELECT (SELECT COUNT(*) FROM labs WHERE id = 1) AS lab, "
            "       (SELECT COUNT(*) FROM projects WHERE id = 1) AS proj, "
            "       (SELECT COUNT(*) FROM users WHERE id = 1) AS owner"
        )
    ).fetchone()
    return bool(row and row.lab and row.proj and row.owner)


def _insert_sample(conn, sample: dict, dry_run: bool) -> bool:
    existing = conn.execute(
        text("SELECT 1 FROM samples WHERE sample_id = :sid"),
        {"sid": sample["sample_id"]},
    ).fetchone()
    if existing:
        return False
    if dry_run:
        return True
    conn.execute(
        text(
            """
            INSERT INTO samples (
                sample_id, lab_id, project_id, owner_id,
                source_type, organism_name, sector,
                type_of_experiment, library_preparation_method,
                sequencing_protocol, sequencing_platform, sequencing_lab,
                date_collected, date_sequenced, collection_facility,
                collection_location_country, collection_location_state,
                fastq_r1_uri,
                scrub_status, pii_scan_status, ingest_method, sharing_level,
                quality_status, surveillance_relevant,
                wwtp_name, population_served, flow_rate_mgd,
                sample_type_ww, sample_matrix, concentration_method
            )
            VALUES (
                :sample_id, 1, 1, 1,
                'wastewater', 'Severe acute respiratory syndrome coronavirus 2', 'wastewater',
                'WHOLE_GENOME_SEQUENCING', 'ARTIC v4.1',
                'https://www.protocols.io/view/artic-v4-1', 'ILLUMINA', 'Example Lab',
                :date_collected, :date_collected, 'Example WWTP',
                'USA', 'Arizona',
                'gs://jackpot-sequences/demo/' || :sample_id || '_R1.fastq.gz',
                'COMPLETE', 'COMPLETE', 'demo_seed', 'PRIVATE',
                'ANALYZABLE', TRUE,
                :wwtp_name, :population_served, :flow_rate_mgd,
                '24-hr-composite', 'raw-influent', 'PEG-precipitation'
            )
            ON CONFLICT (sample_id) DO NOTHING
            """
        ),
        {
            "sample_id": sample["sample_id"],
            "date_collected": sample["date_collected"],
            "wwtp_name": DEMO_SITE,
            "population_served": sample["population_served"],
            "flow_rate_mgd": sample["flow_rate_mgd"],
        },
    )
    return True


def _insert_lineage(conn, sample_id: str, lineage: str, abundance: float, dry_run: bool) -> bool:
    existing = conn.execute(
        text(
            "SELECT 1 FROM wastewater_lineage_abundance "
            "WHERE run_id = :run_id AND sample_id = :sid AND lineage = :lin"
        ),
        {"run_id": DEMO_RUN_ID, "sid": sample_id, "lin": lineage},
    ).fetchone()
    if existing:
        return False
    if dry_run:
        return True
    conn.execute(
        text(
            """
            INSERT INTO wastewater_lineage_abundance (
                run_id, sample_id, lineage, abundance,
                confidence_interval_low, confidence_interval_high,
                coverage_depth, tool_name, tool_version, barcode_version
            )
            VALUES (
                :run_id, :sid, :lin, :ab,
                GREATEST(:ab - 0.04, 0.0), LEAST(:ab + 0.04, 1.0),
                820.0, 'freyja', '1.5.0', '2026-04-15'
            )
            ON CONFLICT (run_id, sample_id, lineage) DO NOTHING
            """
        ),
        {"run_id": DEMO_RUN_ID, "sid": sample_id, "lin": lineage, "ab": abundance},
    )
    return True


def seed(dry_run: bool = True) -> None:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        if not _baseline_present(conn):
            print(
                "Baseline seed not present (labs/projects/users id=1 missing). "
                "Run the baseline migration first."
            )
            return

        samples_inserted = 0
        lineages_inserted = 0
        for sample in SAMPLES:
            if _insert_sample(conn, sample, dry_run):
                samples_inserted += 1
            for lineage, abundance in LINEAGE_MIXTURES[sample["sample_id"]]:
                if _insert_lineage(conn, sample["sample_id"], lineage, abundance, dry_run):
                    lineages_inserted += 1

        if not dry_run:
            conn.commit()

        print("\nWastewater demo seed")
        print(f"  Samples planned: {len(SAMPLES)}")
        print(f"  Samples to insert: {samples_inserted}")
        print(f"  Lineage rows to insert: {lineages_inserted}")
        if dry_run:
            print("\nDRY RUN — no changes written.")
        else:
            print("\nInserted.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed wastewater demo data.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be inserted without writing.",
    )
    args = parser.parse_args()
    seed(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
