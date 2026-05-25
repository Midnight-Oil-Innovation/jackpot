What happens if a user attempts to upload a fastq file and it's actually a fasta file, or vice versa?

Good question, and the honest answer is: it depends on how `file_detector.py` is implemented, and I'd need to look at the actual code to be certain. But I can tell you what the two scenarios look like and which one is more likely given what we know about the architecture.

**If file_detector.py is extension-based only** (which is the more common starting point):

The mismatch gets missed entirely at ingest. The file gets classified as FASTQ based on its `.fastq` extension, passes through `validate_sample()`, gets written to the database with `file_type = "fastq"`, and lands in GCS. The problem only surfaces when a Nextflow pipeline tries to process it — at which point the pipeline fails with a cryptic bioinformatics error, nowhere near the original upload. That's a bad user experience.

**If file_detector.py does content sniffing:**

It reads the first few bytes of the file. FASTQ records start with `@`, FASTA records start with `>`. That's an unambiguous single-byte check. A mismatch would raise an error right at step 2 of the ingest pipeline, the whole transaction rolls back, and the user gets a clear message at upload time rather than a downstream pipeline failure days later.

Given the architecture we've designed, the right behavior is the second one — and it should live in `file_detector.py` specifically because that module is the sole owner of filename and file-type logic. No other part of the system should be making format guesses.

Worth checking the actual implementation and adding a test case for this scenario if it isn't already there. Something like:

```python
def test_file_detector_rejects_fasta_with_fastq_extension(tmp_path):
    # Write a FASTA file with a .fastq extension
    f = tmp_path / "sample_S1_L001_R1_001.fastq"
    f.write_text(">seq1\nACGTACGT\n>seq2\nTTGGCCAA\n")
    with pytest.raises(FileTypeError, match="FASTA content detected in .fastq file"):
        detect_files(tmp_path)
```

That kind of test locks in the desired behavior before someone fixes the extension and forgets the content check exists.

Before writing any integration code, I'd want to read the current `file_detector.py` — the right insertion point depends on how it's structured. But I can tell you exactly what the design should look like, and then we can map it to the actual code.

**Where in the call stack**

The content check should run immediately after extension-based type detection, before any pairing or lane-merging logic. The reason is ordering: pairing logic groups R1/R2 files by filename pattern and assumes the type label is already correct. You want to fail fast on a bad file before doing any of that work.

```
detect_files()
    ↓
_detect_type_from_extension(path)    ← already exists
_validate_content_matches_extension(path, claimed_type)    ← new, goes here
    ↓
_pair_reads()
_merge_lanes()
_group_chunks()
```

**What the function looks like**

```python
import gzip
from pathlib import Path

# Distinctive first bytes for each format
_FORMAT_SIGNATURES: dict[str, bytes] = {
    "fastq": b"@",
    "fasta": b">",
}

def _validate_content_matches_extension(path: Path, claimed_type: str) -> None:
    """
    Read the first byte of the file (handling gzip) and confirm it matches
    the format implied by the file extension. Raises FileDetectorError on mismatch.

    Only runs for fastq/fasta — other types are left to downstream validation.
    """
    expected_sig = _FORMAT_SIGNATURES.get(claimed_type)
    if expected_sig is None:
        return  # not a format we content-sniff

    try:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rb") as fh:
            first_byte = fh.read(1)
    except (OSError, gzip.BadGzipFile) as exc:
        raise FileDetectorError(
            f"Could not read {path.name} to validate format: {exc}"
        ) from exc

    if first_byte != expected_sig:
        actual = "fasta" if first_byte == b">" else \
                 "fastq" if first_byte == b"@" else \
                 f"unknown (first byte: {first_byte!r})"
        raise FileDetectorError(
            f"{path.name} has extension .{claimed_type} but contains "
            f"{actual} content — rename the file or re-export from your sequencer"
        )
```

A few things worth noting in that implementation:

The error message tells the user what to do, not just what went wrong. "Rename the file or re-export from your sequencer" is actionable; "format mismatch" is not.

Gzip handling matters — `.fastq.gz` is the dominant format in production. `gzip.open` decompresses transparently so the same `b"@"` check works for both plain and compressed files. `gzip.BadGzipFile` catches files that claim to be gzipped but aren't.

It only reads one byte. This is on the hot path of every upload, so you want it to be as cheap as possible. One byte is sufficient — `@` and `>` are unambiguous.

It returns silently on unknown types. If someone uploads a BAM or VCF, this function steps aside and lets downstream handle it rather than raising a spurious error.

**The corresponding test**

```python
import gzip
import pytest
from pathlib import Path
from jackpot.business_logic.file_detector import detect_files, FileDetectorError


def test_rejects_fasta_content_with_fastq_extension(tmp_path):
    f = tmp_path / "sample_S1_L001_R1_001.fastq"
    f.write_bytes(b">seq1\nACGTACGT\n>seq2\nTTGGCCAA\n")
    with pytest.raises(FileDetectorError, match="fasta content"):
        detect_files([f])


def test_rejects_fastq_content_with_fasta_extension(tmp_path):
    f = tmp_path / "sample.fasta"
    f.write_bytes(b"@SEQ_ID\nACGT\n+\nIIII\n")
    with pytest.raises(FileDetectorError, match="fastq content"):
        detect_files([f])


def test_rejects_gzipped_fasta_with_fastq_extension(tmp_path):
    f = tmp_path / "sample_S1_L001_R1_001.fastq.gz"
    with gzip.open(f, "wb") as fh:
        fh.write(b">seq1\nACGTACGT\n")
    with pytest.raises(FileDetectorError, match="fasta content"):
        detect_files([f])


def test_accepts_valid_fastq(tmp_path):
    f = tmp_path / "sample_S1_L001_R1_001.fastq"
    f.write_bytes(b"@SEQ_ID\nACGT\n+\nIIII\n")
    result = detect_files([f])
    assert result.file_type == "fastq"


def test_accepts_valid_fasta(tmp_path):
    f = tmp_path / "sample.fasta"
    f.write_bytes(b">seq1\nACGTACGT\n")
    result = detect_files([f])
    assert result.file_type == "fasta"
```

Once you share the actual `file_detector.py`, I can write the precise integration — where to call `_validate_content_matches_extension`, whether `FileDetectorError` already exists or needs to be added, and whether the function receives a `Path` or something else.

Here's the complete design — two new constants, one helper, one validation function that replaces `_validate_content_matches_extension`, and an expanded test suite.

**New additions to `file_detector.py`:**

```python
from __future__ import annotations

import gzip
from pathlib import Path


# ─── Type registries ─────────────────────────────────────────────────────────

SUPPORTED_TYPES: frozenset[str] = frozenset({"fastq", "fasta", "csv", "tsv"})

# Known formats that are on the roadmap but not yet accepted.
# Values are the actionable guidance shown verbatim in the error message.
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
    ".vcf.gz":   "vcf",
    ".fa.gz":    "fasta",
    ".fq.gz":    "fastq",
    ".fastq":    "fastq",
    ".fasta":    "fasta",
    ".fq":       "fastq",
    ".fa":       "fasta",
    ".fna":      "fasta",
    ".bam":      "bam",
    ".cram":     "cram",
    ".vcf":      "vcf",
    ".bcf":      "bcf",
    ".sam":      "sam",
    ".csv":      "csv",
    ".tsv":      "tsv",
    ".txt":      "tsv",
}

# Content signatures for types we sniff: (bytes_to_read, expected_prefix).
# Applied to raw bytes for text formats, decompressed bytes for binary.
_CONTENT_SIGNATURES: dict[str, tuple[int, bytes]] = {
    "fastq": (1,  b"@"),
    "fasta": (1,  b">"),
    "cram":  (4,  b"CRAM"),
    "vcf":   (16, b"##fileformat=VCF"),
    "bam":   (4,  b"BAM\x01"),   # checked after BGZF decompression
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

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
        raise FileDetectorError(
            f"Could not read {path.name}: {exc}"
        ) from exc

    try:
        with open(path, "rb") as fh:
            return fh.read(n)
    except OSError as exc:
        raise FileDetectorError(
            f"Could not read {path.name}: {exc}"
        ) from exc


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


# ─── Main validation entry point ─────────────────────────────────────────────

def validate_file_type(path: Path) -> str:
    """
    Determine and validate the type of path.

    Returns the confirmed type string (e.g. "fastq") on success.

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
        raise FileDetectorError(
            f"{path.name} — {_ROADMAP_TYPES[claimed_type]}"
        )

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
        return claimed_type

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

    return claimed_type
```

------

**Test suite (`tests/test_file_detector_validation.py`):**

```python
import gzip
import pytest
from pathlib import Path

from jackpot.business_logic.file_detector import validate_file_type, FileDetectorError


# ─── Supported types: happy path ─────────────────────────────────────────────

def test_valid_fastq(tmp_path):
    f = tmp_path / "sample_S1_L001_R1_001.fastq"
    f.write_bytes(b"@SEQ_ID\nACGT\n+\nIIII\n")
    assert validate_file_type(f) == "fastq"


def test_valid_fastq_gz(tmp_path):
    f = tmp_path / "sample_S1_L001_R1_001.fastq.gz"
    with gzip.open(f, "wb") as fh:
        fh.write(b"@SEQ_ID\nACGT\n+\nIIII\n")
    assert validate_file_type(f) == "fastq"


def test_valid_fasta(tmp_path):
    f = tmp_path / "reference.fasta"
    f.write_bytes(b">seq1\nACGTACGT\n>seq2\nTTGGCCAA\n")
    assert validate_file_type(f) == "fasta"


def test_valid_fasta_gz(tmp_path):
    f = tmp_path / "reference.fasta.gz"
    with gzip.open(f, "wb") as fh:
        fh.write(b">seq1\nACGTACGT\n")
    assert validate_file_type(f) == "fasta"


def test_valid_csv(tmp_path):
    f = tmp_path / "metadata.csv"
    f.write_bytes(b"sample_id,date_collected\nAZ001,2026-01-15\n")
    assert validate_file_type(f) == "csv"


def test_valid_tsv(tmp_path):
    f = tmp_path / "metadata.tsv"
    f.write_bytes(b"sample_id\tdate_collected\nAZ001\t2026-01-15\n")
    assert validate_file_type(f) == "tsv"


# ─── Content/extension mismatch ──────────────────────────────────────────────

def test_fasta_content_with_fastq_extension(tmp_path):
    f = tmp_path / "sample.fastq"
    f.write_bytes(b">seq1\nACGTACGT\n")
    with pytest.raises(FileDetectorError, match="fasta content"):
        validate_file_type(f)


def test_fastq_content_with_fasta_extension(tmp_path):
    f = tmp_path / "sample.fasta"
    f.write_bytes(b"@SEQ_ID\nACGT\n+\nIIII\n")
    with pytest.raises(FileDetectorError, match="fastq content"):
        validate_file_type(f)


def test_fasta_content_with_fastq_gz_extension(tmp_path):
    f = tmp_path / "sample.fastq.gz"
    with gzip.open(f, "wb") as fh:
        fh.write(b">seq1\nACGTACGT\n")
    with pytest.raises(FileDetectorError, match="fasta content"):
        validate_file_type(f)


# ─── Roadmap types: extension-level rejection ─────────────────────────────────

@pytest.mark.parametrize("filename,match_text", [
    ("sample.bam",  "samtools fastq"),
    ("sample.cram", "samtools fastq"),
    ("sample.vcf",  "planned"),
    ("sample.bcf",  "bcftools view"),
    ("sample.sam",  "samtools fastq"),
    ("calls.vcf.gz","planned"),
])
def test_roadmap_type_rejection(tmp_path, filename, match_text):
    f = tmp_path / filename
    f.write_bytes(b"placeholder")
    with pytest.raises(FileDetectorError, match=match_text):
        validate_file_type(f)


def test_bam_content_with_fastq_extension(tmp_path):
    """A file named .fastq that is actually a BAM should surface the BAM guidance."""
    f = tmp_path / "sample.fastq.gz"
    # Write BGZF-compressed BAM magic
    with gzip.open(f, "wb") as fh:
        fh.write(b"BAM\x01" + b"\x00" * 100)
    with pytest.raises(FileDetectorError, match="samtools fastq"):
        validate_file_type(f)


# ─── Unknown types ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("filename", [
    "results.xlsx",
    "report.pdf",
    "archive.tar.gz",
    "data.h5",
    "noextension",
])
def test_unknown_extension_rejected(tmp_path, filename):
    f = tmp_path / filename
    f.write_bytes(b"placeholder")
    with pytest.raises(FileDetectorError, match="unrecognised extension"):
        validate_file_type(f)


def test_unknown_extension_message_lists_accepted_formats(tmp_path):
    f = tmp_path / "data.xyz"
    f.write_bytes(b"placeholder")
    with pytest.raises(FileDetectorError) as exc_info:
        validate_file_type(f)
    msg = str(exc_info.value)
    assert "fastq" in msg
    assert "fasta" in msg
    assert "contact your lab director" in msg


# ─── Unrecognisable content ───────────────────────────────────────────────────

def test_corrupted_fastq_rejected(tmp_path):
    f = tmp_path / "sample.fastq"
    f.write_bytes(b"CORRUPTED\x00\x01\x02\xff\xfe")
    with pytest.raises(FileDetectorError, match="corrupted or truncated"):
        validate_file_type(f)


def test_empty_file_rejected(tmp_path):
    f = tmp_path / "sample.fastq"
    f.write_bytes(b"")
    with pytest.raises(FileDetectorError, match="corrupted or truncated"):
        validate_file_type(f)
```

------

The key design decisions worth calling out:

The error messages form a deliberate hierarchy. Roadmap types get the most specific message — they include the exact command the user needs to run. Unknown extensions get a mid-tier message that lists what's accepted and who to contact. Corrupted content gets the most cautious message, since we genuinely can't tell if it's a format issue or a transmission problem.

The `validate_file_type` function returns the confirmed type string on success. This means the caller in `file_detector.py` can replace both the extension detection and the old content check with a single call and use the return value directly — no separate `_detect_type_from_extension` call needed downstream.

Adding BAM and VCF support later is a one-line change per format: move the key from `_ROADMAP_TYPES` to `SUPPORTED_TYPES` and add a content signature to `_CONTENT_SIGNATURES`. The error message infrastructure stays in place and automatically stops surfacing for those types.
