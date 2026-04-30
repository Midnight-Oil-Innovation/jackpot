#!/usr/bin/env python3
"""
Seed the reportable_organisms table with a default reference set
of reportable communicable diseases.

The 62-value default set is operator-configurable from P0e onward;
platform admins add/remove organisms via the admin UI at runtime.

Usage:
    python3 scripts/seed_reportable_organisms.py
    python3 scripts/seed_reportable_organisms.py --dry-run
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

# (organism_name, notes)
# Default reference set anchored to NCBI Taxonomy names for
# BioSample/SRA/GenBank/GISAID compatibility.
REPORTABLE_ORGANISMS: list[tuple[str, str]] = [
    # ── Bacteria ─────────────────────────────────────────────────────────────
    ("Bacillus anthracis", "Anthrax"),
    ("Bordetella pertussis", "Pertussis (whooping cough)"),
    ("Borrelia hermsii", "Relapsing fever — tick-borne"),
    ("Borrelia turicatae", "Relapsing fever — tick-borne"),
    ("Brucella abortus", "Brucellosis — bovine"),
    ("Brucella canis", "Brucellosis — canine"),
    ("Brucella melitensis", "Brucellosis — goat/sheep"),
    ("Brucella suis", "Brucellosis — swine"),
    ("Burkholderia mallei", "Glanders"),
    ("Burkholderia pseudomallei", "Melioidosis"),
    ("Clostridium botulinum", "Botulism"),
    ("Clostridium tetani", "Tetanus"),
    ("Corynebacterium diphtheriae", "Diphtheria"),
    ("Coxiella burnetii", "Q fever"),
    ("Cronobacter sakazakii", "Cronobacter infection (infant)"),
    (
        "Escherichia coli",
        "Shiga toxin-producing E. coli (STEC); hemolytic uremic syndrome. "
        "Use serotype field for specific serovar (e.g. O157:H7, O111:H8).",
    ),
    ("Francisella tularensis", "Tularemia"),
    ("Haemophilus ducreyi", "Chancroid"),
    ("Haemophilus influenzae", "Invasive Haemophilus influenzae disease"),
    ("Leptospira interrogans", "Leptospirosis"),
    ("Listeria monocytogenes", "Listeriosis"),
    ("Mycobacterium leprae", "Hansen's disease (leprosy)"),
    ("Mycobacterium tuberculosis", "Tuberculosis — active or latent"),
    ("Mycobacterium bovis", "Tuberculosis — bovine-associated"),
    ("Neisseria gonorrhoeae", "Gonorrhea"),
    ("Neisseria meningitidis", "Invasive meningococcal disease"),
    ("Rickettsia prowazekii", "Epidemic typhus"),
    ("Rickettsia rickettsii", "Rocky Mountain spotted fever (RMSF)"),
    ("Rickettsia typhi", "Murine (endemic) typhus"),
    (
        "Salmonella enterica",
        "Non-typhoidal Salmonella. Use serotype field for serovar "
        "(e.g. Typhimurium, Enteritidis, Newport, Heidelberg).",
    ),
    ("Salmonella Typhi", "Typhoid fever (Salmonella enterica serovar Typhi)"),
    ("Staphylococcus aureus", "Toxic shock syndrome; MRSA — use strain field for MRSA/MSSA"),
    ("Streptococcus pyogenes", "Streptococcal toxic shock syndrome; Group A Streptococcus"),
    ("Treponema pallidum", "Syphilis"),
    ("Vibrio cholerae", "Cholera"),
    ("Yersinia pestis", "Plague — bubonic, septicemic, or pneumonic"),
    # ── Fungi ─────────────────────────────────────────────────────────────────
    ("Candida auris", "Candida auris — multidrug-resistant fungal pathogen"),
    (
        "Coccidioides immitis",
        "Valley fever (coccidioidomycosis). "
        "Default-set inclusion; not on every jurisdiction's reportable list.",
    ),
    (
        "Coccidioides posadasii",
        "Valley fever (coccidioidomycosis). "
        "Default-set inclusion; not on every jurisdiction's reportable list.",
    ),
    # ── Viruses ───────────────────────────────────────────────────────────────
    ("Chikungunya virus", "Chikungunya fever"),
    ("Crimean-Congo hemorrhagic fever orthonairovirus", "Crimean-Congo hemorrhagic fever (CCHF)"),
    ("Dengue virus", "Dengue fever. Use serotype field for DENV-1 through DENV-4."),
    ("Ebola virus", "Ebola virus disease (viral hemorrhagic fever)"),
    (
        "Hantavirus",
        "Hantavirus pulmonary syndrome (HPS) — unspecified hantavirus. "
        "Use Sin Nombre orthohantavirus when species is confirmed.",
    ),
    ("Human immunodeficiency virus 1", "HIV infection; HIV-1"),
    ("Human immunodeficiency virus 2", "HIV infection; HIV-2"),
    ("Influenza A virus", "Influenza — type A. Use strain field for subtype (H1N1, H3N2, H5N1)."),
    ("Influenza B virus", "Influenza — type B. Use strain field for lineage (Victoria, Yamagata)."),
    ("Lassa virus", "Lassa fever (viral hemorrhagic fever)"),
    ("Lymphocytic choriomeningitis virus", "Lymphocytic choriomeningitis (LCM)"),
    ("Marburg virus", "Marburg virus disease (viral hemorrhagic fever)"),
    ("Measles virus", "Measles (rubeola)"),
    ("MERS-CoV", "Middle East respiratory syndrome coronavirus"),
    (
        "Mpox virus",
        "Mpox (formerly monkeypox). Use strain field for clade (hMPXV Clade I or hMPXV Clade II).",
    ),
    ("Mumps virus", "Mumps"),
    (
        "Poliovirus",
        "Poliomyelitis. Use serotype field for type (1, 2, 3). "
        "Use strain field for wild vs. vaccine-derived.",
    ),
    (
        "Rabies lyssavirus",
        "Rabies. Use strain field for variant (e.g. bat variant, skunk variant, fox variant).",
    ),
    (
        "Respiratory syncytial virus",
        "RSV — included under 'Respiratory disease (outbreak)' category. "
        "Use strain field for RSV-A or RSV-B.",
    ),
    ("Rubella virus", "Rubella (German measles)"),
    ("SARS-CoV", "Severe acute respiratory syndrome (SARS, 2003)"),
    (
        "Severe acute respiratory syndrome coronavirus 2",
        "COVID-19 (novel coronavirus infection). NCBI standard name for SARS-CoV-2. "
        "Use pango_lineage field for Pangolin lineage designation.",
    ),
    (
        "Sin Nombre orthohantavirus",
        "Hantavirus pulmonary syndrome — Sin Nombre virus",
    ),
    ("St. Louis encephalitis virus", "St. Louis encephalitis"),
    ("Vaccinia virus", "Vaccinia-related adverse event (smallpox vaccine)"),
    ("Variola virus", "Smallpox"),
    ("Varicella-zoster virus", "Varicella (chickenpox); herpes zoster (shingles)"),
    ("West Nile virus", "West Nile virus disease"),
    ("Yellow fever virus", "Yellow fever"),
    ("Zika virus", "Zika virus infection"),
    # ── Parasites ─────────────────────────────────────────────────────────────
    (
        "Naegleria fowleri",
        "Primary amoebic meningoencephalitis (PAM). "
        "Free-living protozoan parasite found in warm freshwater.",
    ),
    ("Taenia saginata", "Taeniasis — beef tapeworm"),
    ("Taenia solium", "Taeniasis and cysticercosis — pork tapeworm"),
    ("Toxoplasma gondii", "Toxoplasmosis; parasitic encephalitis"),
    ("Trichinella spiralis", "Trichinosis"),
    # ── Novel / Emerging ──────────────────────────────────────────────────────
    (
        "novel pathogen",
        "Reportable category: 'Emerging or exotic disease'. "
        "Use when a novel pathogen is identified but has no stable NCBI Taxonomy name yet. "
        "Platform Admin assigns permanent name when NCBI Taxonomy provides one.",
    ),
]


def seed(dry_run: bool = True) -> None:
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        existing = {
            row[0] for row in conn.execute(text("SELECT organism_name FROM reportable_organisms"))
        }

        to_insert = [(n, d) for n, d in REPORTABLE_ORGANISMS if n not in existing]
        already_present = len(REPORTABLE_ORGANISMS) - len(to_insert)

        print("\nReportable organisms seed")
        print(f"  Total in list:      {len(REPORTABLE_ORGANISMS)}")
        print(f"  Already in DB:      {already_present}")
        print(f"  To insert:          {len(to_insert)}")

        if dry_run:
            print("\nDRY RUN — no changes written.")
            for name, _ in to_insert:
                print(f"  would insert: {name}")
            return

        for name, notes in to_insert:
            conn.execute(
                text(
                    "INSERT INTO reportable_organisms (organism_name, notes) "
                    "VALUES (:name, :notes) "
                    "ON CONFLICT (organism_name) DO NOTHING"
                ),
                {"name": name, "notes": notes},
            )
        conn.commit()
        print(f"\nInserted {len(to_insert)} organisms.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed reportable_organisms table.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be inserted without writing.",
    )
    args = parser.parse_args()
    seed(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
