"""
JACKPOT file pairing detector.
Single source of truth for all file extension and naming convention logic.
Called by the ingest router to populate sample_files and convenience URI fields.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

# ── Supported extensions ─────────────────────────────────────────────────────
# Add new extensions here ONLY. Every regex pattern uses FASTQ_EXT automatically.

_FASTQ_BASES = r"fastq|fq"
_FASTA_BASES = r"fasta|fa|fna"
_ALL_BASES = rf"(?:{_FASTQ_BASES}|{_FASTA_BASES})"
_COMPRESSION = r"(?:\.gz|\.bz2)?"

FASTQ_EXT = rf"\.(?:{_ALL_BASES}){_COMPRESSION}"

_EXT_TO_FILE_TYPE: dict[str, str] = {
    "fastq": "FASTQ",
    "fq": "FASTQ",
    "fasta": "FASTA",
    "fa": "FASTA",
    "fna": "FASTA",
}


def get_file_type(filename: str) -> str:
    """Return FASTQ, FASTA, or OTHER from a filename."""
    name = filename.lower()
    for suffix in (".gz", ".bz2"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return _EXT_TO_FILE_TYPE.get(Path(name).suffix.lstrip("."), "OTHER")


def is_sequence_file(filename: str) -> bool:
    return get_file_type(filename) in ("FASTQ", "FASTA")


# ── Pairing patterns — ordered most-specific to least-specific ───────────────

PAIRED_PATTERNS: list[re.Pattern] = [
    re.compile(
        rf"^(?P<prefix>.+?)_(?P<lane>L\d+)_(?P<dir>R[12])(?:_\d+)?{FASTQ_EXT}$", re.IGNORECASE
    ),
    re.compile(rf"^(?P<prefix>.+?)_(?P<dir>R[12])(?:_\d+)?{FASTQ_EXT}$", re.IGNORECASE),
    re.compile(rf"^(?P<prefix>.+?)_(?P<dir>[12]){FASTQ_EXT}$"),
    re.compile(rf"^(?P<prefix>.+?)_reads_(?P<dir>[12]){FASTQ_EXT}$"),
    re.compile(rf"^(?P<prefix>.+?)_(?P<dir>forward|reverse){FASTQ_EXT}$", re.IGNORECASE),
]

CHUNK_PATTERN = re.compile(
    rf"^(?P<prefix>.+?)_(?P<idx>\d{{1,4}}){FASTQ_EXT}$",
    re.IGNORECASE,
)

DIRECTION_MAP: dict[str, str] = {
    "r1": "R1",
    "1": "R1",
    "forward": "R1",
    "r2": "R2",
    "2": "R2",
    "reverse": "R2",
}


@dataclass
class DetectedFile:
    filename: str
    file_type: str = "FASTQ"
    library_layout: str = "UNPAIRED"
    read_direction: str | None = None
    lane: str | None = None
    chunk_index: int | None = None
    prefix: str | None = None


@dataclass
class DetectionResult:
    files: list[DetectedFile]
    warnings: list[str] = field(default_factory=list)
    has_paired: bool = False
    has_unpaired: bool = False
    lane_count: int = 0


def detect_files(filenames: list[str]) -> DetectionResult:
    """Analyse filenames for a single sample. Non-sequence files skipped."""
    seq_files = [f for f in filenames if is_sequence_file(f)]
    skipped = [f for f in filenames if not is_sequence_file(f)]
    detected: list[DetectedFile] = []
    warnings: list[str] = []

    if skipped:
        warnings.append(
            f"Skipped {len(skipped)} non-sequence file(s): "
            f"{', '.join(skipped[:5])}{'...' if len(skipped) > 5 else ''}"
        )

    groups: dict[tuple[str, str | None], dict[str, str]] = {}
    unmatched: list[str] = []

    for fname in seq_files:
        matched = False
        for pattern in PAIRED_PATTERNS:
            m = pattern.match(fname)
            if m:
                gd = m.groupdict()
                prefix = gd.get("prefix", "")
                lane = gd.get("lane")
                direction = DIRECTION_MAP.get(gd.get("dir", "").lower(), gd.get("dir", "").upper())
                key = (prefix, lane)
                groups.setdefault(key, {})
                if direction in groups[key]:
                    warnings.append(
                        f"Duplicate {direction} for '{prefix}'"
                        f"{f', lane {lane}' if lane else ''}: "
                        f"'{groups[key][direction]}' and '{fname}'"
                    )
                groups[key][direction] = fname
                matched = True
                break
        if not matched:
            unmatched.append(fname)

    has_paired = False
    has_unpaired = False
    lanes: set[str] = set()

    for (prefix, lane), dir_map in groups.items():
        has_r1, has_r2 = "R1" in dir_map, "R2" in dir_map
        if has_r1 and has_r2:
            has_paired = True
            if lane:
                lanes.add(lane)
            for direction, fname in dir_map.items():
                detected.append(
                    DetectedFile(
                        filename=fname,
                        file_type=get_file_type(fname),
                        library_layout="PAIRED",
                        read_direction=direction,
                        lane=lane,
                        prefix=prefix,
                    )
                )
        elif has_r1:
            warnings.append(f"R1 '{dir_map['R1']}' has no R2 — single-end.")
            has_unpaired = True
            detected.append(
                DetectedFile(
                    filename=dir_map["R1"],
                    file_type=get_file_type(dir_map["R1"]),
                    library_layout="SINGLE",
                    read_direction="R1",
                    lane=lane,
                    prefix=prefix,
                )
            )
        else:
            warnings.append(f"R2 '{dir_map['R2']}' has no R1 — orphaned.")
            has_unpaired = True
            detected.append(
                DetectedFile(
                    filename=dir_map["R2"],
                    file_type=get_file_type(dir_map["R2"]),
                    library_layout="SINGLE",
                    read_direction="R2",
                    lane=lane,
                    prefix=prefix,
                )
            )

    chunk_groups: dict[str, list[tuple[int, str]]] = {}
    truly_unmatched: list[str] = []

    for fname in unmatched:
        m = CHUNK_PATTERN.match(fname)
        if m:
            chunk_groups.setdefault(m.group("prefix"), []).append((int(m.group("idx")), fname))
        else:
            truly_unmatched.append(fname)

    for prefix, chunks in chunk_groups.items():
        has_unpaired = True
        for idx, fname in sorted(chunks):
            detected.append(
                DetectedFile(
                    filename=fname,
                    file_type=get_file_type(fname),
                    library_layout="UNPAIRED",
                    chunk_index=idx,
                    prefix=prefix,
                )
            )

    for fname in truly_unmatched:
        has_unpaired = True
        detected.append(
            DetectedFile(
                filename=fname,
                file_type=get_file_type(fname),
                library_layout="UNPAIRED",
            )
        )
        warnings.append(f"'{fname}' did not match any known convention — registered as unpaired.")

    return DetectionResult(
        files=detected,
        warnings=warnings,
        has_paired=has_paired,
        has_unpaired=has_unpaired,
        lane_count=len(lanes),
    )


def get_convenience_uris(
    result: DetectionResult,
    uri_map: dict[str, str],
) -> tuple[str | None, str | None]:
    """Return (fastq_r1_uri, fastq_r2_uri) convenience values for samples table."""
    r1_files = sorted(
        [f for f in result.files if f.read_direction == "R1"],
        key=lambda f: (f.lane or "", f.chunk_index or 0),
    )
    r2_files = sorted(
        [f for f in result.files if f.read_direction == "R2"],
        key=lambda f: (f.lane or "", f.chunk_index or 0),
    )
    r1_uri = uri_map.get(r1_files[0].filename) if r1_files else None
    r2_uri = uri_map.get(r2_files[0].filename) if r2_files else None
    if r1_uri is None and result.files:
        r1_uri = uri_map.get(result.files[0].filename)
    return r1_uri, r2_uri
