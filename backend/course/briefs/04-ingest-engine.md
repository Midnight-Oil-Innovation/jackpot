# Module 4: The Ingest Engine

### Teaching Arc
- **Metaphor:** Airport baggage screening — your bag goes through X-ray (harmonizer translates labels), security check (validator enforces rules), customs declaration (quality tier assigned), and finally gets a baggage tag with a tracking number (JACKPOT URI minted) before reaching the carousel (database).
- **Opening hook:** "A researcher uploads a spreadsheet from their lab. That spreadsheet might call the same field 'Sample ID' or 'Specimen No.' or 'ID' depending on which lab made it. How does JACKPOT understand all of them?"
- **Key insight:** Real-world data is messy. The ingest pipeline separates concerns: *translation* (harmonizer maps column names), *validation* (validator enforces rules), and *enrichment* (epiweek, quality tier, URI minted). Each step is independent and testable.
- **"Why should I care?":** When a batch upload fails, the error message will name one of these steps. Knowing "harmonizer warning" vs. "validator error" vs. "quality tier PRELIMINARY" tells you exactly what to fix — and what AI to ask for help with.

### Code Snippets (pre-extracted)

**File: backend/harmonizer.py (lines 50-98) — the translator:**
```python
def harmonize_row(raw: dict[str, Any], mapping: dict) -> dict[str, Any]:
    column_map: dict[str, str] = mapping.get("column_mappings", {})
    result: dict[str, Any] = {}

    for raw_key, value in raw.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        schema_key = column_map.get(raw_key, raw_key)
        result[schema_key] = value.strip() if isinstance(value, str) else value

    return result


def harmonize_csv(
    rows: list[dict[str, Any]],
    mapping_name: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    mapping = load_mapping(mapping_name)
    column_map: dict[str, str] = mapping.get("column_mappings", {})
    harmonized: list[dict[str, Any]] = []
    warnings: list[str] = []

    if rows:
        unknown = [k for k in rows[0] if k not in column_map and k not in column_map.values()]
        if unknown:
            warnings.append(
                f"Unknown columns not in mapping '{mapping_name}': "
                f"{unknown}. They will be passed through unchanged."
            )

    for row in rows:
        harmonized.append(harmonize_row(row, mapping))

    return harmonized, warnings
```

**File: backend/validator.py (lines 113-165) — the gatekeeper:**
```python
def validate_sample(data: dict) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    for field_name in BASE_REQUIRED:
        val = data.get(field_name)
        if val is None or (isinstance(val, str | list) and not val):
            errors.append(f"Missing required field: {field_name}")

    source_type = data.get("source_type", "")
    if source_type and source_type not in VALID_SOURCE_TYPES:
        errors.append(
            f"Invalid source_type '{source_type}'. Must be one of: {sorted(VALID_SOURCE_TYPES)}"
        )

    raw_date = data.get("date_collected")
    if raw_date:
        try:
            collected = date.fromisoformat(raw_date)
            if collected > date.today():
                errors.append("date_collected cannot be in the future.")
            elif (date.today() - collected).days > 365 * 5:
                warnings.append("date_collected is more than 5 years in the past.")
        except ValueError:
            errors.append(f"date_collected '{raw_date}' is not a valid ISO 8601 date.")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
```

**File: backend/validator.py (lines 264-296) — quality tier computation:**
```python
def compute_quality_status(data: dict, validation_result: ValidationResult) -> str:
    if not validation_result.valid:
        return "PRELIMINARY"

    tier3_fields = [
        "originating_lab", "submitting_lab",
        "collection_location_state", "collection_location_county",
        "host_age", "host_sex",
    ]
    if all(data.get(f) for f in tier3_fields):
        return "SUBMITTABLE"

    tier2_fields = ["collection_location_state"]
    precision = data.get("date_collected_precision", "day")
    if precision != "year" and all(data.get(f) for f in tier2_fields):
        return "ANALYZABLE"

    return "PRELIMINARY"
```

**File: backend/epiweek.py (full file):**
```python
from datetime import date
from epiweeks import Week

def compute_epiweeks(
    date_collected: date,
    precision: str = "day",
) -> dict[str, int | None]:
    if precision in ("year", "month"):
        return {
            "mmwr_year": None, "mmwr_week": None,
            "iso_year": None, "iso_week": None,
        }
    mmwr = Week.fromdate(date_collected, system="CDC")
    iso = Week.fromdate(date_collected, system="ISO")
    return {
        "mmwr_year": mmwr.year,
        "mmwr_week": mmwr.week,
        "iso_year": iso.year,
        "iso_week": iso.week,
    }
```

**File: backend/validator.py (lines 299-324) — surveillance relevance:**
```python
def compute_surveillance_relevant(
    organism_name: str,
    target_organisms: list[str] | None,
    reportable_organisms: set[str],
) -> bool:
    if organism_name in reportable_organisms:
        return True

    if organism_name == "metagenome":
        if not target_organisms:
            return True  # conservative default
        return any(t in reportable_organisms for t in target_organisms)

    return False
```

### Interactive Elements

- [x] **Code↔English translation** — harmonize_row: show how one CSV row with lab-specific column names gets translated to schema fields
- [x] **Code↔English translation** — compute_quality_status: show the three-tier logic as a decision tree
- [x] **Data flow animation** — actors: CSV Upload, Harmonizer, Validator, Epiweek Engine, URI Minter, Database. Steps: (1) Raw CSV arrives with lab-specific columns → (2) Harmonizer maps column names → (3) Validator checks required fields → validation error stops flow, warnings pass through → (4) Epiweek computed from date_collected → (5) Quality tier assigned (PRELIMINARY/ANALYZABLE/SUBMITTABLE) → (6) surveillance_relevant computed → (7) JACKPOT URI minted → (8) Record written to database
- [x] **Group chat** — actors: Harmonizer, Validator, Quality Engine. Scenario: a row comes in with "Specimen No." (unmapped column), missing date_sequenced, and present state/county fields. Harmonizer passes it with a warning. Validator rejects it (missing date_sequenced). Shows the difference between errors (stop) and warnings (continue).
- [x] **Quiz** — 3 questions:
  1. "A researcher uploads a CSV where 'FASTQ files' column is empty. The sample still ingests successfully. How is that possible?" (not a required field — FASTQ file location is optional at ingest, can be added later)
  2. "A sample is marked ANALYZABLE. What does that unlock that PRELIMINARY doesn't?" (time-series charts and geographic maps on the dashboard — ANALYZABLE has state + month-precision date)
  3. "The validator returns errors=[] but warnings=['date_collected is more than 5 years in the past']. Does the sample ingest?" (yes — warnings don't block ingest, only errors do)
- [x] **Glossary tooltips** — ingest, harmonizer, validator, controlled vocabulary, ISO 8601, MMWR epiweek, quality tier, surveillance_relevant, URI, metagenome

### Reference Files to Read
- `references/interactive-elements.md` → "Message Flow / Data Flow Animation", "Group Chat Animation", "Code ↔ English Translation Blocks", "Multiple-Choice Quizzes", "Glossary Tooltips"
- `references/content-philosophy.md` → full file
- `references/gotchas.md` → full file

### Connections
- **Previous module:** "Auth & Identity" — showed how users authenticate; this module shows what authenticated users DO (upload data)
- **Next module:** "Data Layer" — shows where validated data ends up (PostgreSQL tables and storage buckets)
- **Tone/style notes:** Accent vermillion (#D94F30). Module 4 uses --color-bg-warm (#F5F0E8). Three quality tiers: PRELIMINARY (tier 1), ANALYZABLE (tier 2), SUBMITTABLE (tier 3).
