"""M2-PRE-1 — canonical scope-URI builder (access_model.md §3.1.1, ADR 0015).

The builder's job is to make ``engine._scope_contains`` meaningful: prefix
containment is only correct when every scope in the system is a path under one
root. These tests pin the shape, the ancestor requirement, and the containment
relation the shape is supposed to produce.
"""

import pytest

from backend.authz.engine import _scope_contains
from backend.authz.scope import ROOT, scope_uri


class TestShape:
    def test_root(self):
        assert scope_uri() == "instance://self"

    def test_each_level(self):
        assert scope_uri(org=3) == "instance://self/org/3"
        assert scope_uri(org=3, lab=7) == "instance://self/org/3/lab/7"
        assert scope_uri(org=3, lab=7, project=12) == "instance://self/org/3/lab/7/project/12"
        assert (
            scope_uri(org=3, lab=7, project=12, sample=55)
            == "instance://self/org/3/lab/7/project/12/sample/55"
        )

    def test_every_scope_is_rooted(self):
        # One root per deployment. A peer instance is a principal, not a
        # branch (§3.3), so no builder input can produce a second root.
        for kwargs in ({}, {"org": 1}, {"org": 1, "lab": 2}):
            assert scope_uri(**kwargs).startswith(ROOT)


class TestAncestorsRequired:
    @pytest.mark.parametrize(
        "kwargs, missing",
        [
            ({"lab": 7}, "org"),
            ({"project": 12}, "org"),
            ({"org": 3, "project": 12}, "lab"),
            ({"org": 3, "lab": 7, "sample": 55}, "project"),
        ],
    )
    def test_level_without_its_ancestors_raises(self, kwargs, missing):
        with pytest.raises(ValueError, match=missing):
            scope_uri(**kwargs)


class TestIdValidation:
    @pytest.mark.parametrize("bad", ["3", "3/lab/7", 3.0, None.__class__])
    def test_non_int_id_rejected(self, bad):
        # A string id could carry a separator and forge containment.
        with pytest.raises(TypeError):
            scope_uri(org=bad)

    def test_bool_rejected(self):
        # bool is an int subclass; would render as "org/True".
        with pytest.raises(TypeError):
            scope_uri(org=True)

    @pytest.mark.parametrize("bad", [0, -1])
    def test_non_positive_id_rejected(self, bad):
        with pytest.raises(ValueError, match="positive"):
            scope_uri(org=bad)


class TestContainment:
    """The property the whole ADR exists for."""

    def test_instance_contains_every_level(self):
        for deeper in (
            scope_uri(org=3),
            scope_uri(org=3, lab=7),
            scope_uri(org=3, lab=7, project=12),
            scope_uri(org=3, lab=7, project=12, sample=55),
        ):
            assert _scope_contains(scope_uri(), deeper)

    def test_admin_root_grant_reaches_a_lab_scoped_sample(self):
        # The exact cell that made admin-bypass-vs-scoped-grants a cutover
        # blocker: instance://self did not contain lab://N.
        assert _scope_contains(scope_uri(), scope_uri(org=3, lab=7, project=12, sample=55))

    def test_org_contains_its_labs_but_not_another_org(self):
        assert _scope_contains(scope_uri(org=3), scope_uri(org=3, lab=7))
        assert not _scope_contains(scope_uri(org=3), scope_uri(org=4, lab=7))

    def test_lab_does_not_contain_a_sibling_lab(self):
        assert not _scope_contains(scope_uri(org=3, lab=7), scope_uri(org=3, lab=8))

    def test_containment_is_one_directional(self):
        assert not _scope_contains(scope_uri(org=3, lab=7), scope_uri(org=3))

    def test_segment_boundary_not_fooled_by_id_prefix(self):
        # lab/7 must not contain lab/70 — the trap pure string prefixing falls
        # into and the reason _scope_contains appends a separator.
        assert not _scope_contains(scope_uri(org=3, lab=7), scope_uri(org=3, lab=70))
        assert not _scope_contains(scope_uri(org=1), scope_uri(org=11, lab=2))
