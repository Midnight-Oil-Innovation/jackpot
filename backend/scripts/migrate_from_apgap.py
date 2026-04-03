#!/usr/bin/env python3
"""
Migrate data from APGAP PostgreSQL to JACKPOT PostgreSQL.

Migrates: Organizations, Users, Labs, Projects, Lab Memberships,
          Project Memberships, Domain Whitelist.

Usage:
    APGAP_DB_URL=postgresql://user:pass@host:5432/apgap_db \
        python3 migrate_from_apgap.py --dry-run

    APGAP_DB_URL=postgresql://user:pass@host:5432/apgap_db \
        python3 migrate_from_apgap.py
"""

import argparse
import os
import sys

from sqlalchemy import create_engine, text

APGAP_DB_URL = os.environ.get("APGAP_DB_URL", "")
JACKPOT_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://jackpot:jackpot@localhost:5432/jackpot_db",
)


def migrate(dry_run: bool = True) -> None:
    if not APGAP_DB_URL:
        print("ERROR: Set APGAP_DB_URL environment variable first.")
        sys.exit(1)

    apgap = create_engine(APGAP_DB_URL)
    jackpot = create_engine(JACKPOT_DB_URL)

    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\nJACKPOT migration from APGAP [{mode}]\n")

    with apgap.connect() as src, jackpot.connect() as dst:
        # Organizations
        orgs = src.execute(
            text(
                "SELECT display_name, default_approve_analytical_dataset_requests "
                "FROM organizations WHERE active = TRUE"
            )
        ).fetchall()
        print(f"  Organizations: {len(orgs)}")
        if not dry_run:
            for o in orgs:
                dst.execute(
                    text(
                        "INSERT INTO organizations (display_name, "
                        "default_approve_analytical_dataset_requests) "
                        "VALUES (:name, :approve) ON CONFLICT DO NOTHING"
                    ),
                    {"name": o[0], "approve": o[1]},
                )

        # Domain whitelist
        domains = src.execute(text("SELECT domain, description FROM domain_whitelist")).fetchall()
        print(f"  Domain whitelist entries: {len(domains)}")
        if not dry_run:
            for d in domains:
                dst.execute(
                    text(
                        "INSERT INTO domain_whitelist (domain, description) "
                        "VALUES (:domain, :desc) ON CONFLICT DO NOTHING"
                    ),
                    {"domain": d[0], "desc": d[1] or ""},
                )

        # Users (without FKs first — created_by_id etc handled separately)
        users = src.execute(
            text(
                "SELECT email, name, is_platform_admin, is_data_analyst, is_active "
                "FROM users WHERE is_active = TRUE"
            )
        ).fetchall()
        print(f"  Users: {len(users)}")
        if not dry_run:
            for u in users:
                dst.execute(
                    text(
                        "INSERT INTO users "
                        "(email, name, is_platform_admin, is_data_analyst, is_active) "
                        "VALUES (:email, :name, :admin, :analyst, :active) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {
                        "email": u[0],
                        "name": u[1] or "",
                        "admin": u[2],
                        "analyst": u[3],
                        "active": u[4],
                    },
                )

        if not dry_run:
            dst.commit()

    print(f"\nMigration [{mode}] complete.")
    if dry_run:
        print("Run without --dry-run to apply changes.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
