"""
Tests for validate_file_type() — content sniffing in file_detector.py.

Covers:
  - Happy path: valid FASTQ, FASTA, CSV, TSV (plain and gzipped)
  - Content/extension mismatches (the core protection)
  - Roadmap type rejection at extension level
  - Roadmap type detected via content sniffing (misnamed file)
  - Unknown/unrecognised extensions
  - Corrupted or truncated files
  - Empty files
"""

import gzip

import pytest

from backend.file_detector import FileDetectorError, validate_file_type

# ─── Supported types: happy path ─────────────────────────────────────────────


def test_valid_fastq(tmp_path):
    f = tmp_path / "sample_S1_L001_R1_001.fastq"
    f.write_bytes(b"@SEQ_ID\nACGT\n+\nIIII\n")
    assert validate_file_type(f) == "FASTQ"


def test_valid_fastq_fq_extension(tmp_path):
    f = tmp_path / "sample_R1.fq"
    f.write_bytes(b"@SEQ_ID\nACGT\n+\nIIII\n")
    assert validate_file_type(f) == "FASTQ"


def test_valid_fastq_gz(tmp_path):
    f = tmp_path / "sample_S1_L001_R1_001.fastq.gz"
    with gzip.open(f, "wb") as fh:
        fh.write(b"@SEQ_ID\nACGT\n+\nIIII\n")
    assert validate_file_type(f) == "FASTQ"


def test_valid_fasta(tmp_path):
    f = tmp_path / "reference.fasta"
    f.write_bytes(b">seq1\nACGTACGT\n>seq2\nTTGGCCAA\n")
    assert validate_file_type(f) == "FASTA"


def test_valid_fasta_fa_extension(tmp_path):
    f = tmp_path / "reference.fa"
    f.write_bytes(b">seq1\nACGTACGT\n")
    assert validate_file_type(f) == "FASTA"


def test_valid_fasta_fna_extension(tmp_path):
    f = tmp_path / "genome.fna"
    f.write_bytes(b">seq1\nACGTACGT\n")
    assert validate_file_type(f) == "FASTA"


def test_valid_fasta_gz(tmp_path):
    f = tmp_path / "reference.fasta.gz"
    with gzip.open(f, "wb") as fh:
        fh.write(b">seq1\nACGTACGT\n")
    assert validate_file_type(f) == "FASTA"


def test_valid_csv(tmp_path):
    f = tmp_path / "metadata.csv"
    f.write_bytes(b"sample_id,date_collected\nAZ001,2026-01-15\n")
    assert validate_file_type(f) == "CSV"


def test_valid_tsv(tmp_path):
    f = tmp_path / "metadata.tsv"
    f.write_bytes(b"sample_id\tdate_collected\nAZ001\t2026-01-15\n")
    assert validate_file_type(f) == "TSV"


def test_valid_txt_as_tsv(tmp_path):
    """A .txt file maps to TSV (no content sniffing for tabular formats)."""
    f = tmp_path / "metadata.txt"
    f.write_bytes(b"sample_id\tdate_collected\nAZ001\t2026-01-15\n")
    assert validate_file_type(f) == "TSV"


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


def test_fastq_content_with_fasta_gz_extension(tmp_path):
    f = tmp_path / "reference.fasta.gz"
    with gzip.open(f, "wb") as fh:
        fh.write(b"@SEQ_ID\nACGT\n+\nIIII\n")
    with pytest.raises(FileDetectorError, match="fastq content"):
        validate_file_type(f)


def test_fasta_content_with_fq_extension(tmp_path):
    f = tmp_path / "sample.fq"
    f.write_bytes(b">seq1\nACGTACGT\n")
    with pytest.raises(FileDetectorError, match="fasta content"):
        validate_file_type(f)


# ─── Roadmap types: extension-level rejection ────────────────────────────────


@pytest.mark.parametrize(
    "filename,match_text",
    [
        ("sample.bam", "samtools fastq"),
        ("sample.cram", "samtools fastq"),
        ("sample.vcf", "planned"),
        ("sample.bcf", "bcftools view"),
        ("sample.sam", "samtools fastq"),
        ("calls.vcf.gz", "planned"),
    ],
)
def test_roadmap_type_rejection(tmp_path, filename, match_text):
    f = tmp_path / filename
    f.write_bytes(b"placeholder")
    with pytest.raises(FileDetectorError, match=match_text):
        validate_file_type(f)


# ─── Roadmap type detected via content sniffing ──────────────────────────────


def test_bam_content_with_fastq_gz_extension(tmp_path):
    """A file named .fastq.gz that is actually a BAM should surface BAM guidance."""
    f = tmp_path / "sample.fastq.gz"
    # Write BGZF-compressed BAM magic bytes
    with gzip.open(f, "wb") as fh:
        fh.write(b"BAM\x01" + b"\x00" * 100)
    with pytest.raises(FileDetectorError, match="samtools fastq"):
        validate_file_type(f)


def test_cram_content_with_fasta_extension(tmp_path):
    """A file named .fasta that is actually CRAM should surface CRAM guidance."""
    f = tmp_path / "reference.fasta"
    f.write_bytes(b"CRAM" + b"\x00" * 100)
    with pytest.raises(FileDetectorError, match="samtools fastq"):
        validate_file_type(f)


# ─── Unknown extensions ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "filename",
    [
        "results.xlsx",
        "report.pdf",
        "archive.tar.gz",
        "data.h5",
        "noextension",
    ],
)
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
    assert "contact your lab director" in msg.lower()


# ─── Unrecognisable / corrupted content ──────────────────────────────────────


def test_corrupted_fastq_rejected(tmp_path):
    f = tmp_path / "sample.fastq"
    f.write_bytes(b"CORRUPTED\x00\x01\x02\xff\xfe")
    with pytest.raises(FileDetectorError, match="corrupted or truncated"):
        validate_file_type(f)


def test_empty_fastq_file_rejected(tmp_path):
    f = tmp_path / "sample.fastq"
    f.write_bytes(b"")
    with pytest.raises(FileDetectorError, match="corrupted or truncated"):
        validate_file_type(f)


def test_empty_fasta_file_rejected(tmp_path):
    f = tmp_path / "reference.fasta"
    f.write_bytes(b"")
    with pytest.raises(FileDetectorError, match="corrupted or truncated"):
        validate_file_type(f)


def test_whitespace_only_fastq_rejected(tmp_path):
    """A file with only whitespace is not valid FASTQ."""
    f = tmp_path / "sample.fastq"
    f.write_bytes(b"\n\n\n")
    with pytest.raises(FileDetectorError, match="corrupted or truncated"):
        validate_file_type(f)


# ─── Edge cases ──────────────────────────────────────────────────────────────


def test_csv_skips_content_sniffing(tmp_path):
    """CSV/TSV have no content signature — extension is trusted."""
    f = tmp_path / "metadata.csv"
    f.write_bytes(b">this looks like fasta but the extension says csv\n")
    assert validate_file_type(f) == "CSV"


def test_fq_gz_valid(tmp_path):
    """Short extension .fq.gz is handled correctly."""
    f = tmp_path / "reads.fq.gz"
    with gzip.open(f, "wb") as fh:
        fh.write(b"@SEQ\nACGT\n+\nIIII\n")
    assert validate_file_type(f) == "FASTQ"


def test_fa_gz_valid(tmp_path):
    """Short extension .fa.gz is handled correctly."""
    f = tmp_path / "ref.fa.gz"
    with gzip.open(f, "wb") as fh:
        fh.write(b">seq1\nACGTACGT\n")
    assert validate_file_type(f) == "FASTA"


def test_fna_gz_valid(tmp_path):
    """Extension .fna.gz is handled correctly."""
    f = tmp_path / "genome.fna.gz"
    with gzip.open(f, "wb") as fh:
        fh.write(b">chr1\nACGTACGT\n")
    assert validate_file_type(f) == "FASTA"
