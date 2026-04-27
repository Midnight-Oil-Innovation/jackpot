import pytest

from backend.file_detector import (
    detect_files,
    get_convenience_uris,
    get_file_type,
)


@pytest.mark.parametrize(
    "filename,expected_type",
    [
        ("sample_R1.fastq", "FASTQ"),
        ("sample_R1.fastq.gz", "FASTQ"),
        ("sample_R1.fastq.bz2", "FASTQ"),
        ("sample_R1.fq", "FASTQ"),
        ("sample_R1.fq.gz", "FASTQ"),
        ("sample_R1.fq.bz2", "FASTQ"),
        ("assembly.fa", "FASTA"),
        ("assembly.fa.gz", "FASTA"),
        ("assembly.fna", "FASTA"),
        ("assembly.fna.gz", "FASTA"),
        ("assembly.fasta", "FASTA"),
        ("assembly.fasta.gz", "FASTA"),
        ("SAMPLE.FASTQ.GZ", "FASTQ"),
        ("report.html", "OTHER"),
        ("metadata.csv", "OTHER"),
    ],
)
def test_get_file_type(filename, expected_type):
    assert get_file_type(filename) == expected_type


@pytest.mark.parametrize(
    "r1,r2",
    [
        ("sample_R1.fastq.gz", "sample_R2.fastq.gz"),
        ("sample_R1.fq.gz", "sample_R2.fq.gz"),
        ("sample_R1.fq.bz2", "sample_R2.fq.bz2"),
        ("sample_R1.fasta.gz", "sample_R2.fasta.gz"),
        ("sample_R1.fa.gz", "sample_R2.fa.gz"),
        ("sample_R1.fna.gz", "sample_R2.fna.gz"),
        ("sample_1.fastq.gz", "sample_2.fastq.gz"),
        ("sample_1.fq.gz", "sample_2.fq.gz"),
        ("sample_reads_1.fq", "sample_reads_2.fq"),
        ("sample_forward.fa.gz", "sample_reverse.fa.gz"),
    ],
)
def test_paired_detection(r1, r2):
    result = detect_files([r1, r2])
    assert result.has_paired, f"Expected paired: {result.warnings}"
    assert not result.warnings


def test_multilane_illumina():
    files = [
        "sample_L001_R1_001.fastq.gz",
        "sample_L001_R2_001.fastq.gz",
        "sample_L002_R1_001.fastq.gz",
        "sample_L002_R2_001.fastq.gz",
    ]
    result = detect_files(files)
    assert result.has_paired
    assert result.lane_count == 2


def test_nanopore_chunks():
    files = [f"barcode01_{i}.fq.gz" for i in (0, 4, 8, 12)]
    result = detect_files(files)
    assert result.has_unpaired
    assert not result.has_paired
    assert all(f.chunk_index is not None for f in result.files)


def test_r1_without_r2_warns():
    result = detect_files(["sample_R1.fastq.gz"])
    assert result.has_unpaired
    assert any("R2" in w for w in result.warnings)


def test_non_sequence_files_skipped():
    result = detect_files(
        [
            "sample_R1.fastq.gz",
            "sample_R2.fastq.gz",
            "metadata.csv",
        ]
    )
    assert len(result.files) == 2
    assert any("Skipped" in w for w in result.warnings)


def test_convenience_uris_simple_paired():
    result = detect_files(["EX-001_R1.fastq.gz", "EX-001_R2.fastq.gz"])
    uri_map = {
        "EX-001_R1.fastq.gz": "gs://bucket/EX-001_R1.fastq.gz",
        "EX-001_R2.fastq.gz": "gs://bucket/EX-001_R2.fastq.gz",
    }
    r1, r2 = get_convenience_uris(result, uri_map)
    assert r1 is not None and "R1" in r1
    assert r2 is not None and "R2" in r2


@pytest.mark.parametrize(
    "filenames",
    [
        [],
        [""],
        ["single.fastq.gz"],
        ["a.fastq.gz", "b.fastq.gz", "c.fastq.gz"],
    ],
)
def test_never_raises(filenames):
    result = detect_files(filenames)
    assert isinstance(result.has_paired, bool)
    assert isinstance(result.warnings, list)
