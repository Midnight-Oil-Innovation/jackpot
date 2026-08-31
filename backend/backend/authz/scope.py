"""Canonical scope-URI construction (access_model.md §3.1.1, ADR 0015).

Every scope reference — in a grant, in a policy, and for a resource — is a
path under one root. There is exactly one root per deployment, spelled
``instance://self``: a scope ref is only ever interpreted inside the instance
that stores it, and federation peers are principals rather than branches of
the tree (§3.3).

    instance://self
    instance://self/org/3
    instance://self/org/3/lab/7
    instance://self/org/3/lab/7/project/12
    instance://self/org/3/lab/7/project/12/sample/55

Containment is unchanged by this module: ``engine._scope_contains`` matches on
equality or a prefix at a segment boundary, which is exactly what a single
rooted path makes correct. Building the strings in one place is what keeps the
prefix relation meaningful — the four hand-written shapes that preceded this
(``instance://field-laptop/org-x/…``, ``org://acme/lab-1/…``,
``instance://self``, ``lab://7``) could not contain one another at all.
"""

ROOT = "instance://self"

# Ordered outermost-first; a level may only be given when every level above it
# is also given, which is what makes the resulting path a real ancestor chain.
_LEVELS = ("org", "lab", "project", "sample")


def scope_uri(
    *,
    org: int | None = None,
    lab: int | None = None,
    project: int | None = None,
    sample: int | None = None,
) -> str:
    """Build the canonical scope URI for a level of the tree.

    ``scope_uri()`` is the instance root. Each deeper level requires its
    ancestors: ``scope_uri(lab=7)`` raises, because a lab's path runs through
    its org and a grant written without it would not be contained by any
    org-scoped grant.

    Ids must be positive ``int`` — the database's own SERIAL keys. Anything
    else is rejected rather than coerced: a string id could carry a ``/`` and
    silently forge containment (``org/3/lab/7`` from ``org="3/lab/7"``), and
    ``bool`` is an ``int`` subclass that would render as ``org/True``.
    """
    parts = [ROOT]
    missing: str | None = None
    for level, value in zip(_LEVELS, (org, lab, project, sample), strict=True):
        if value is None:
            missing = missing or level
            continue
        if missing is not None:
            raise ValueError(
                f"{level}={value} given without {missing} — a scope path must "
                f"name every level above it (§3.1.1)"
            )
        if type(value) is not int:
            raise TypeError(f"{level} id must be int, got {type(value).__name__}: {value!r}")
        if value < 1:
            raise ValueError(f"{level} id must be a positive database id, got {value}")
        parts.append(f"{level}/{value}")
    return "/".join(parts)
