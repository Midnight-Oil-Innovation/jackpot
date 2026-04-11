#!/usr/bin/env python3
"""
Seed the sequencing_labs table with known sequencing facilities.

Usage:
    uv run python3 scripts/seed_sequencing_labs.py
    uv run python3 scripts/seed_sequencing_labs.py --dry-run
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://jackpot:jackpot@localhost:5432/jackpot_db",  # pragma: allowlist secret
)

# (name, organization, is_external)
SEQUENCING_LABS: list[tuple[str, str, bool]] = [
    ("Sonora Quest Laboratories", "Sonora Quest Laboratories", True),
    ("Laboratory Corporation of America", "Laboratory Corporation of America", True),
    ("Otero Outpost", "Arizona State University", False),
]


def seed(dry_run: bool = True) -> None:
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        existing = {row[0] for row in conn.execute(text("SELECT name FROM sequencing_labs"))}

        to_insert = [(name, org, ext) for name, org, ext in SEQUENCING_LABS if name not in existing]
        already_present = len(SEQUENCING_LABS) - len(to_insert)

        print("\nSequencing labs seed")
        print(f"  Total in list:      {len(SEQUENCING_LABS)}")
        print(f"  Already in DB:      {already_present}")
        print(f"  To insert:          {len(to_insert)}")

        if dry_run:
            print("\nDRY RUN — no changes written.")
            for name, org, _ in to_insert:
                print(f"  would insert: {name} ({org})")
            return

        for name, org, ext in to_insert:
            conn.execute(
                text(
                    "INSERT INTO sequencing_labs (name, organization, is_external) "
                    "VALUES (:name, :org, :ext) "
                    "ON CONFLICT (name) DO NOTHING"
                ),
                {"name": name, "org": org, "ext": ext},
            )
        conn.commit()
        print(f"\nInserted {len(to_insert)} sequencing labs.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed sequencing_labs table.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be inserted without writing.",
    )
    args = parser.parse_args()
    seed(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
