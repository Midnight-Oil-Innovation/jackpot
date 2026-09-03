"""URI scheme recognition (B-DRS-URI-1).

`drs://` was listed as a recognised scheme while nothing in the tree could
dereference one: `backend/backend/storage/factory.py` only ever returns
`S3StorageBackend` — S3-compatible when `storage_endpoint` is set, otherwise
GCS via HMAC — and no DRS client exists anywhere. Recognising a scheme
JACKPOT cannot read told a submitter their URI was fine when no pipeline
could ever open it. The decision recorded in
B-DRS-URI-1 was to reject rather than resolve, so DRS now warns like any
other unsupported scheme.
"""

import pytest

from backend.validator import RESOLVABLE_URI_SCHEMES, validate_sample


def _uri_warnings(result):
    return [w for w in result.warnings if "recognised URI scheme" in w]


@pytest.mark.parametrize("scheme", RESOLVABLE_URI_SCHEMES)
def test_schemes_a_storage_backend_can_open_are_recognised(valid_human_sample, scheme):
    """Derived from the constant on purpose, so a newly supported scheme is
    covered the moment it is added. The negative cases below stay hardcoded —
    generating those from the same constant would test nothing."""
    uri = f"{scheme}bucket/x_R1.fastq.gz"
    result = validate_sample({**valid_human_sample, "fastq_r1_uri": uri})
    assert not _uri_warnings(result), f"{uri} should be recognised"


def test_drs_is_not_recognised(valid_human_sample):
    """The whole of this item: drs:// must warn, not pass silently."""
    result = validate_sample({**valid_human_sample, "fastq_r1_uri": "drs://ex.org/abc123"})
    # The warning is the canary: it is what fails if _check_uri_schemes stops
    # firing at all, which the constant assertion alone would not catch.
    assert _uri_warnings(result), "drs:// passed as recognised — nothing can dereference it"
    assert "drs://" not in RESOLVABLE_URI_SCHEMES


def test_rejection_is_a_warning_not_an_error(valid_human_sample):
    """Scheme recognition has always been advisory; rejecting DRS must not
    quietly promote it to a hard gate and break ingest of everything else."""
    result = validate_sample({**valid_human_sample, "fastq_r1_uri": "drs://ex.org/abc123"})
    assert not any("URI scheme" in e for e in result.errors)


@pytest.mark.parametrize("uri", ["file:///srv/x.fastq", "/srv/seq/x.fastq", "ftp://h/x.fastq"])
def test_other_unsupported_schemes_still_warn(valid_human_sample, uri):
    """Pins that DRS is not special-cased — it joins the unsupported set."""
    assert _uri_warnings(validate_sample({**valid_human_sample, "fastq_r1_uri": uri}))
