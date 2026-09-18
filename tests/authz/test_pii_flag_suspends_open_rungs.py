"""Critical Rule 43's query half — a flagged sample stops being open (§2.4).

Rule 43: a PII-flagged sample is "stored but blocked from queries, pipelines,
and export until a Lab Director overrides or the submitter fixes the flagged
fields". #264 built the pipeline and export gates; #265 built the override.
This is the query gate.

The rule cannot be a DENY. Deny-wins is strict and admits no exception, so a
DENY on ``sample:read_detail`` for a flagged row would also blind the two
people Rule 43 names as the way out — the submitter who must edit the field
and the Lab Director who must release it. What must stop is narrower: the
rungs that open a row to principals with no tie to it at all.

``LADDER_POLICIES`` splits cleanly along that line. PUBLIC, DISCOVERABLE and
surveillance-relevance are facts about the row that let a stranger read it;
``owner_id`` and the lab-scoped grants are the row's own people. So the
suspension is a resource predicate on the first group and nothing on the
second — no new verb, no new column, no migration.

Both halves are exercised here for the reason the sibling file states: a
policy that exists in only one of ``permit()`` and ``visibility_sql_clause``
is the divergence M1 was built to prevent.
"""

import sqlite3

import pytest

from authz.scopes import INSTANCE, SCOPE_EXPR
from backend.authz import (
    CapabilityGrant,
    Context,
    Decision,
    Principal,
    PrincipalKind,
    Resource,
    permit,
    visibility_sql_clause,
)
from backend.authz.policy import LADDER_POLICIES
from backend.authz.principal import _SAMPLE_LINEAGE_SQL, SAMPLE_ATTRIBUTE_COLUMNS
from backend.authz.scope import scope_uri

OWNER_ID = 7

# (sharing_level, surveillance_relevant, owner_id, pii_scan_status). Each pair
# is the same row twice, once clean and once flagged, so a verdict that does
# not move is a verdict the flag did not reach.
ROWS = [
    ("PUBLIC", False, 100, "COMPLETE"),
    ("PUBLIC", False, 100, "PII_DETECTED"),
    ("DISCOVERABLE", False, 100, "COMPLETE"),
    ("DISCOVERABLE", False, 100, "PII_DETECTED"),
    ("PRIVATE", True, 100, "COMPLETE"),
    ("PRIVATE", True, 100, "PII_DETECTED"),
    ("PRIVATE", False, OWNER_ID, "PII_DETECTED"),
    ("PUBLIC", False, 100, "OVERRIDDEN"),
]


def _principal(uid=str(OWNER_ID), grants=()):
    return Principal(
        kind=PrincipalKind.HUMAN,
        id=uid,
        on_behalf_of=None,
        grants=[CapabilityGrant(c, s) for c, s in grants],
    )


def _resource(row, i):
    sharing, surveillance, owner, pii = row
    return Resource(
        scope=scope_uri(org=1, lab=1, project=2, sample=i),
        attributes={
            "sharing_level": sharing,
            "surveillance_relevant": surveillance,
            "owner_id": owner,
            "pii_scan_status": pii,
        },
    )


def _sql_visible(principal, capability):
    """Row ids the SQL half admits, over the same fixture rows."""
    frag, params = visibility_sql_clause(
        principal,
        capability,
        SCOPE_EXPR,
        policies=LADDER_POLICIES,
        attribute_columns=SAMPLE_ATTRIBUTE_COLUMNS,
    )
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE labs (id INTEGER PRIMARY KEY, organization_id INTEGER)")
    conn.execute(
        "CREATE TABLE samples (id INTEGER PRIMARY KEY, lab_id INTEGER, project_id INTEGER, "
        "sharing_level TEXT, surveillance_relevant BOOLEAN, owner_id INTEGER, "
        "pii_scan_status TEXT)"
    )
    conn.execute("INSERT INTO labs (id, organization_id) VALUES (1, 1)")
    for i, (sharing, surveillance, owner, pii) in enumerate(ROWS, start=1):
        conn.execute(
            "INSERT INTO samples (id, lab_id, project_id, sharing_level, "
            "surveillance_relevant, owner_id, pii_scan_status) "
            "VALUES (?, 1, 2, ?, ?, ?, ?)",
            (i, sharing, 1 if surveillance else 0, owner, pii),
        )
    got = {
        r[0]
        for r in conn.execute(
            f"SELECT s.id FROM samples s JOIN labs l ON l.id = s.lab_id WHERE {frag}", params
        )
    }
    conn.close()
    return got


STRANGER = _principal(uid="999")
SURVEILLANCE_OFFICER = _principal(uid="999", grants=[("sample:read_surveillance", INSTANCE)])
OWNER = _principal()
LAB_MEMBER = _principal(uid="999", grants=[("sample:read_detail", scope_uri(org=1, lab=1))])


def _permits(principal, capability, row, i=1):
    return (
        permit(principal, capability, _resource(row, i), Context(), policies=LADDER_POLICIES)
        is Decision.ALLOW
    )


class TestTheOpenRungsCloseOnAFlaggedRow:
    @pytest.mark.parametrize("capability", ["sample:read", "sample:read_detail"])
    def test_public_stops_being_readable_by_a_stranger(self, capability):
        assert _permits(STRANGER, capability, ("PUBLIC", False, 100, "COMPLETE"))
        assert not _permits(STRANGER, capability, ("PUBLIC", False, 100, "PII_DETECTED"))

    def test_discoverable_stops_being_list_visible(self):
        """The federation query surface: §7.4 hands a peer exactly this rung."""
        assert _permits(STRANGER, "sample:read", ("DISCOVERABLE", False, 100, "COMPLETE"))
        assert not _permits(STRANGER, "sample:read", ("DISCOVERABLE", False, 100, "PII_DETECTED"))

    @pytest.mark.parametrize("capability", ["sample:read", "sample:read_detail"])
    def test_surveillance_relevance_stops_carrying_the_row(self, capability):
        assert _permits(SURVEILLANCE_OFFICER, capability, ("PRIVATE", True, 100, "COMPLETE"))
        assert not _permits(
            SURVEILLANCE_OFFICER, capability, ("PRIVATE", True, 100, "PII_DETECTED")
        )

    def test_overridden_is_open_again(self):
        """Closes #265's loop at this end rather than inferring it.

        Every Rule 43 gate tests ``== 'PII_DETECTED'`` and this one is a
        ``{"not": ...}`` against the same constant, so OVERRIDDEN passes for
        the same reason — but that is an argument, and this is a test.
        """
        assert _permits(STRANGER, "sample:read_detail", ("PUBLIC", False, 100, "OVERRIDDEN"))


class TestTheRowsOwnPeopleKeepSeeingIt:
    """Rule 43's two exits both require reading the flagged sample first."""

    @pytest.mark.parametrize("capability", ["sample:read", "sample:read_detail"])
    def test_the_owner_still_sees_their_own_flagged_sample(self, capability):
        assert _permits(OWNER, capability, ("PRIVATE", False, OWNER_ID, "PII_DETECTED"))

    def test_a_lab_scoped_grant_still_covers_a_flagged_sample(self):
        """The Lab Director's path to the override, and the lab's to the fix."""
        assert _permits(LAB_MEMBER, "sample:read_detail", ("PRIVATE", False, 100, "PII_DETECTED"))


class TestTheSqlHalfAgrees:
    @pytest.mark.parametrize(
        ("principal", "capability"),
        [
            (STRANGER, "sample:read"),
            (STRANGER, "sample:read_detail"),
            (SURVEILLANCE_OFFICER, "sample:read"),
            (SURVEILLANCE_OFFICER, "sample:read_detail"),
            (OWNER, "sample:read_detail"),
            (LAB_MEMBER, "sample:read_detail"),
        ],
    )
    def test_row_wise_and_sql_reach_the_same_verdict(self, principal, capability):
        expected = {
            i for i, row in enumerate(ROWS, start=1) if _permits(principal, capability, row, i)
        }
        assert _sql_visible(principal, capability) == expected


def test_the_flag_is_loaded_as_an_attribute():
    """Rule 74 canary: the suspension is silent if the column is not read.

    A ``{"not": "PII_DETECTED"}`` predicate over an attribute the resource
    does not carry evaluates TRUE — absent is not equal to anything — so the
    rungs above would go on firing exactly as they did before and every test
    in this file would still pass through ``_resource``, which supplies the
    attribute by hand. What decides it in production is the guard's own
    lineage query. Assert that, not the fixture.
    """
    assert SAMPLE_ATTRIBUTE_COLUMNS["pii_scan_status"] == "s.pii_scan_status"
    assert "s.pii_scan_status" in _SAMPLE_LINEAGE_SQL
