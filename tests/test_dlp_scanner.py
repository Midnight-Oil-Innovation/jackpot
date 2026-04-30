"""
Tests for the DLP metadata scanner.

All tests run with DLP_ENABLED=false (default), testing the
local-dev bypass path, field discovery, content building,
offset mapping, and redaction logic.
"""

from backend.dlp_scanner import (
    DLPFinding,
    DLPScanResult,
    _build_content_item,
    _is_exception,
    _likelihood_meets_threshold,
    _offset_to_field,
    _redact_matched_text,
    get_scannable_fields,
    scan_batch_metadata,
    scan_sample_metadata,
)


class TestRedaction:
    """Test matched text redaction for audit logging."""

    def test_redact_normal_text(self):
        assert _redact_matched_text("John Smith") == "J********h"

    def test_redact_short_text(self):
        assert _redact_matched_text("AB") == "**"

    def test_redact_single_char(self):
        assert _redact_matched_text("X") == "*"

    def test_redact_empty(self):
        assert _redact_matched_text("") == ""

    def test_redact_three_chars(self):
        assert _redact_matched_text("ABC") == "A*C"


class TestLikelihoodThreshold:
    """Test likelihood comparison logic."""

    def test_likely_meets_threshold(self):
        assert _likelihood_meets_threshold("LIKELY") is True

    def test_very_likely_meets_threshold(self):
        assert _likelihood_meets_threshold("VERY_LIKELY") is True

    def test_possible_below_threshold(self):
        assert _likelihood_meets_threshold("POSSIBLE") is False

    def test_unlikely_below_threshold(self):
        assert _likelihood_meets_threshold("UNLIKELY") is False

    def test_unknown_value(self):
        assert _likelihood_meets_threshold("BOGUS") is False


class TestFieldExceptions:
    """Test that expected PII fields are excluded."""

    def test_pi_name_person_name_is_exception(self):
        assert _is_exception("pi_name", "PERSON_NAME") is True

    def test_pi_name_email_is_not_exception(self):
        assert _is_exception("pi_name", "EMAIL_ADDRESS") is False

    def test_sample_id_person_name_is_not_exception(self):
        assert _is_exception("sample_id", "PERSON_NAME") is False

    def test_unknown_field_is_not_exception(self):
        assert _is_exception("notes", "PERSON_NAME") is False


class TestContentBuilding:
    """Test building the DLP content string from sample metadata."""

    def test_builds_content_from_string_fields(self):
        sample = {"sample_id": "EX-001", "strain": "Delta", "host_age": 45}
        scannable = {"sample_id", "strain"}
        content, offsets = _build_content_item(sample, scannable)
        assert "[sample_id]: EX-001" in content
        assert "[strain]: Delta" in content
        assert "host_age" not in content  # not in scannable set

    def test_skips_none_and_empty(self):
        sample = {"sample_id": None, "strain": "", "isolate": "  "}
        scannable = {"sample_id", "strain", "isolate"}
        content, offsets = _build_content_item(sample, scannable)
        assert content == ""

    def test_offsets_map_correctly(self):
        sample = {"sample_id": "EX-001", "strain": "Delta"}
        scannable = {"sample_id", "strain"}
        content, offsets = _build_content_item(sample, scannable)
        for field_name, (start, end) in offsets.items():
            chunk = content[start:end]
            assert f"[{field_name}]:" in chunk


class TestOffsetMapping:
    """Test mapping character offsets back to field names."""

    def test_maps_to_correct_field(self):
        offsets = {"sample_id": (0, 25), "strain": (25, 45)}
        assert _offset_to_field(10, offsets) == "sample_id"
        assert _offset_to_field(30, offsets) == "strain"

    def test_unknown_offset(self):
        offsets = {"sample_id": (0, 25)}
        assert _offset_to_field(100, offsets) == "unknown"


class TestScannableFields:
    """Test dynamic field discovery from JSON Schema."""

    def test_returns_set(self):
        fields = get_scannable_fields()
        assert isinstance(fields, set)

    def test_includes_known_free_text_fields(self):
        fields = get_scannable_fields()
        # These are string fields without enum backing
        for expected in ["sample_id", "strain", "collection_facility"]:
            assert expected in fields, f"Expected {expected} in scannable fields"

    def test_excludes_enum_fields(self):
        fields = get_scannable_fields()
        # These are enum-backed fields that should NOT be scanned
        for excluded in ["source_type", "sequencing_platform", "sector"]:
            assert excluded not in fields, f"{excluded} should not be scannable"


class TestScanSampleMetadata:
    """Test the main scan function (local dev bypass)."""

    def test_returns_clean_when_disabled(self):
        sample = {"sample_id": "John Smith", "strain": "test@email.com"}
        result = scan_sample_metadata(sample)
        assert result.clean is True
        assert result.findings == []
        assert result.error is None
        assert result.scan_time_ms == 0.0

    def test_result_is_correct_type(self):
        result = scan_sample_metadata({"sample_id": "EX-001"})
        assert isinstance(result, DLPScanResult)


class TestScanBatchMetadata:
    """Test batch scanning (local dev bypass)."""

    def test_returns_clean_for_all_samples(self):
        samples = [
            {"sample_id": "EX-001", "strain": "Delta"},
            {"sample_id": "EX-002", "strain": "Omicron"},
            {"sample_id": "EX-003", "strain": "Alpha"},
        ]
        results = scan_batch_metadata(samples)
        assert len(results) == 3
        assert all(r.clean for r in results.values())
        assert "EX-001" in results
        assert "EX-002" in results
        assert "EX-003" in results

    def test_handles_missing_sample_id(self):
        samples = [{"strain": "Delta"}]
        results = scan_batch_metadata(samples)
        assert len(results) == 1


class TestDLPFinding:
    """Test the DLPFinding dataclass."""

    def test_finding_creation(self):
        f = DLPFinding(
            field_name="sample_id",
            info_type="PERSON_NAME",
            likelihood="LIKELY",
            matched_text="J********h",
            quote_offset=15,
        )
        assert f.field_name == "sample_id"
        assert f.info_type == "PERSON_NAME"


class TestDLPScanResult:
    """Test the DLPScanResult dataclass."""

    def test_clean_result(self):
        r = DLPScanResult(clean=True)
        assert r.clean is True
        assert r.findings == []
        assert r.error is None

    def test_flagged_result(self):
        finding = DLPFinding(
            field_name="sample_id",
            info_type="PERSON_NAME",
            likelihood="LIKELY",
            matched_text="J********h",
            quote_offset=15,
        )
        r = DLPScanResult(clean=False, findings=[finding])
        assert r.clean is False
        assert len(r.findings) == 1

    def test_error_result(self):
        r = DLPScanResult(clean=False, error="API timeout")
        assert r.clean is False
        assert r.error == "API timeout"
