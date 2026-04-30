"""
JACKPOT file pairing detector.
Single source of truth for all file extension and naming convention logic.
Called by the ingest router to populate sample_files and convenience URI fields.

validate_file_type() — confirms a file's content matches its extension.
detect_files()        — groups filenames into paired/unpaired/chunked samples.
get_convenience_uris() — extracts R1/R2 URIs for the samples table.
"""

import gzip
import re
from dataclasses import dataclass, field
from pathlib import Path

# ── Custom exception ─────────────────────────────────────────────────────────


class FileDetectorError(Exception):
    """Raised when a file cannot be identified or fails content validation."""


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


# ── File type validation (content sniffing) ──────────────────────────────────
#
# validate_file_type() reads the first 1–16 bytes of a file to confirm its
# content matches the extension. Called by the ingest router on each uploaded
# file BEFORE filenames are passed to detect_files() for pairing.
#
# Ingest router usage:
#
#     for path in uploaded_paths:
#         file_type = validate_file_type(path)   # raises FileDetectorError
#     filenames = [p.name for p in uploaded_paths]
#     result = detect_files(filenames)

SUPPORTED_TYPES: frozenset[str] = frozenset({"fastq", "fasta", "csv", "tsv"})

# Known formats on the roadmap but not yet accepted.
# Values are actionable guidance shown verbatim in the error message.
_ROADMAP_TYPES: dict[str, str] = {
    "bam": (
        "BAM files are not yet accepted directly. Convert to FASTQ first:\n"
        "  samtools fastq sample.bam -1 R1.fastq -2 R2.fastq\n"
        "BAM support is planned for a future release."
    ),
    "cram": (
        "CRAM files are not yet accepted. Convert to FASTQ first:\n"
        "  samtools fastq sample.cram -1 R1.fastq -2 R2.fastq\n"
        "CRAM support is planned for a future release."
    ),
    "vcf": (
        "VCF files are not yet accepted. VCF/BCF support is planned.\n"
        "Contact your lab director if this is time-sensitive."
    ),
    "bcf": (
        "BCF files are not yet accepted. Convert to VCF first:\n"
        "  bcftools view sample.bcf -o sample.vcf\n"
        "BCF/VCF support is planned for a future release."
    ),
    "sam": (
        "SAM files are not yet accepted. Convert to FASTQ first:\n"
        "  samtools fastq sample.sam -1 R1.fastq -2 R2.fastq"
    ),
}

# Maps file extensions (including compound ones like .fastq.gz) to type strings.
# Listed longest-first so .fastq.gz is matched before .gz.
_EXTENSION_MAP: dict[str, str] = {
    ".fastq.gz": "fastq",
    ".fasta.gz": "fasta",
    ".vcf.gz": "vcf",
    ".fa.gz": "fasta",
    ".fq.gz": "fastq",
    ".fna.gz": "fasta",
    ".fastq": "fastq",
    ".fasta": "fasta",
    ".fq": "fastq",
    ".fa": "fasta",
    ".fna": "fasta",
    ".bam": "bam",
    ".cram": "cram",
    ".vcf": "vcf",
    ".bcf": "bcf",
    ".sam": "sam",
    ".csv": "csv",
    ".tsv": "tsv",
    ".txt": "tsv",
}

# Content signatures for types we sniff: (bytes_to_read, expected_prefix).
# Applied to decompressed bytes for gzipped files.
_CONTENT_SIGNATURES: dict[str, tuple[int, bytes]] = {
    "fastq": (1, b"@"),
    "fasta": (1, b">"),
    "cram": (4, b"CRAM"),
    "vcf": (16, b"##fileformat=VCF"),
    "bam": (4, b"BAM\x01"),  # checked after BGZF decompression
}


def _type_from_extension(path: Path) -> str | None:
    """
    Return the type string for path based on its extension(s), or None if
    the extension is not in _EXTENSION_MAP.

    Checks compound extensions (.fastq.gz) before simple ones (.gz).
    """
    name = path.name.lower()
    for ext, file_type in _EXTENSION_MAP.items():
        if name.endswith(ext):
            return file_type
    return None


def _read_first_bytes(path: Path, n: int) -> bytes:
    """
    Read the first n bytes of path, decompressing gzip/BGZF transparently.
    Raises FileDetectorError if the file cannot be read.
    """
    try:
        # Try gzip first — covers .fastq.gz, .fasta.gz, and BAM (BGZF)
        with gzip.open(path, "rb") as fh:
            return fh.read(n)
    except gzip.BadGzipFile:
        pass
    except OSError as exc:
        raise FileDetectorError(f"Could not read {path.name}: {exc}") from exc

    try:
        with open(path, "rb") as fh:
            return fh.read(n)
    except OSError as exc:
        raise FileDetectorError(f"Could not read {path.name}: {exc}") from exc


def _sniff_type_from_content(path: Path) -> str | None:
    """
    Return the type string that best matches the file's content, or None
    if the content does not match any known signature.

    Only checks types listed in _CONTENT_SIGNATURES.
    """
    for file_type, (n_bytes, signature) in _CONTENT_SIGNATURES.items():
        try:
            first_bytes = _read_first_bytes(path, n_bytes)
        except FileDetectorError:
            return None
        if first_bytes == signature:
            return file_type
    return None


def validate_file_type(path: Path) -> str:
    """
    Determine and validate the type of a file by checking both its extension
    and its content.

    Returns the confirmed type string in UPPERCASE (e.g. "FASTQ") on success.

    Raises FileDetectorError with an actionable message when:
      - The extension maps to an unsupported roadmap type (e.g. .bam)
      - The extension is completely unrecognised
      - The file content does not match what the extension claims
      - The content suggests a roadmap type despite a different extension
      - The content is unrecognisable (possible corruption)
    """
    claimed_type = _type_from_extension(path)

    # ── Case 1: extension maps to a recognised but unsupported type ──────────
    if claimed_type in _ROADMAP_TYPES:
        raise FileDetectorError(f"{path.name} — {_ROADMAP_TYPES[claimed_type]}")

    # ── Case 2: extension is completely unknown ───────────────────────────────
    if claimed_type is None:
        suffix = path.suffix or "(no extension)"
        accepted = ", ".join(sorted(SUPPORTED_TYPES))
        raise FileDetectorError(
            f"{path.name} has an unrecognised extension ({suffix}). "
            f"JACKPOT currently accepts: {accepted}. "
            f"If you believe this format should be supported, contact your "
            f"lab director or open a support request."
        )

    # ── Case 3: extension is a supported type — verify content ───────────────
    if claimed_type not in _CONTENT_SIGNATURES:
        # csv/tsv: no content signature defined, trust the extension
        return claimed_type.upper()

    actual_type = _sniff_type_from_content(path)

    if actual_type is None:
        # Content did not match any known signature
        raise FileDetectorError(
            f"{path.name} has extension .{claimed_type} but its content "
            f"could not be recognised as any known format. "
            f"The file may be corrupted or truncated. "
            f"Re-export from your sequencer and try again."
        )

    if actual_type in _ROADMAP_TYPES:
        # e.g. a file named sample.fastq that is actually a BAM
        raise FileDetectorError(
            f"{path.name} has extension .{claimed_type} but contains "
            f"{actual_type.upper()} content.\n"
            f"{_ROADMAP_TYPES[actual_type]}"
        )

    if actual_type != claimed_type:
        raise FileDetectorError(
            f"{path.name} has extension .{claimed_type} but contains "
            f"{actual_type} content. "
            f"Rename the file or re-export from your sequencer."
        )

    return claimed_type.upper()


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
