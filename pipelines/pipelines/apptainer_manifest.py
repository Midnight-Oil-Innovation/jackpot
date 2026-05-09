"""Apptainer image manifest reader (P0h H-2).

Each pipeline wrapper directory ships an ``apptainer_images.txt`` listing
the OCI image references the pipeline pulls when running under
``apptainer.enabled = true``. This module is the canonical reader and
exists so a future ``jackpot images export`` CLI has one parser to call
across the whole zoo, instead of every caller re-implementing a "strip
comments, split lines" loop.

Format
------

The file is line-oriented. Encoding is UTF-8.

- One OCI image reference per line. References may be any string the
  Apptainer / Docker runtimes accept, e.g.
  ``docker.io/library/python:3.12-slim-bookworm``,
  ``quay.io/biocontainers/samtools:1.20--h50ea8bc_0``, or
  ``oras://ghcr.io/foo/bar:1.0``.
- Lines starting with ``#`` are comments; ignored entirely.
- Lines starting with ``@`` are directives. The current directives are
  ``@upstream <slug>`` and ``@upstream-config <url>``; both are
  metadata used by the audit doc and ignored by the reader. Unknown
  directives are tolerated (logged at debug level by callers if they
  care) so the format can grow without breaking older readers.
- Blank lines are tolerated and ignored.
- Trailing whitespace is stripped; inline comments (``image:tag # foo``)
  are NOT supported — keep one URI per line.

The reader returns an :class:`ApptainerManifest` carrying both the
image list and the directive metadata, so callers that need the
upstream slug (for ``jackpot images audit <pipeline>``) can find it
without reparsing the file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

_PIPELINE_PKG_DIR = Path(__file__).resolve().parent
_MANIFEST_FILENAME = "apptainer_images.txt"


@dataclass(frozen=True)
class ApptainerManifest:
    """Parsed view of one ``apptainer_images.txt`` file.

    ``images`` preserves source order so callers that pre-pull images
    in a deterministic sequence get a deterministic sequence.
    """

    pipeline: str
    images: tuple[str, ...]
    directives: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def upstream(self) -> str | None:
        """Return the value of the first ``@upstream`` directive, if any."""
        for name, value in self.directives:
            if name == "upstream":
                return value
        return None


def parse_manifest_text(text: str, *, pipeline: str) -> ApptainerManifest:
    """Parse the contents of an ``apptainer_images.txt`` body.

    Stand-alone of the filesystem so callers can feed a string directly
    (test fixtures, CLI ``--stdin`` paths, etc.). The file-loading
    helper :func:`load_manifest` is the typical entry point.
    """
    images: list[str] = []
    directives: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            # @directive value...   →   ('directive', 'value...')
            head, _, value = line[1:].partition(" ")
            directives.append((head.strip(), value.strip()))
            continue
        images.append(line)
    return ApptainerManifest(
        pipeline=pipeline,
        images=tuple(images),
        directives=tuple(directives),
    )


def load_manifest(pipeline: str, *, root: Path | None = None) -> ApptainerManifest:
    """Read ``<root>/<pipeline>/apptainer_images.txt`` and parse it.

    ``root`` defaults to the package-level directory containing this
    module (i.e. the directory holding ``viralrecon/``, ``cecret/``,
    etc.). Pass ``root`` for tests using a temporary directory.

    Raises
    ------
    FileNotFoundError
        If the manifest file is missing. Pipelines that do not yet ship
        a manifest are surfaced as a clear error rather than silently
        returning an empty list, because an empty list is a legitimate
        outcome for "this pipeline really pulls nothing" — distinct
        from "no manifest present yet".
    """
    base = root if root is not None else _PIPELINE_PKG_DIR
    path = base / pipeline / _MANIFEST_FILENAME
    return parse_manifest_text(path.read_text(encoding="utf-8"), pipeline=pipeline)


def list_pipelines_with_manifests(*, root: Path | None = None) -> list[str]:
    """Return the sorted list of pipelines with an ``apptainer_images.txt``.

    Skips entries that aren't directories or that don't contain a
    manifest. Used by ``jackpot images export --all`` to enumerate
    pre-staging targets.
    """
    base = root if root is not None else _PIPELINE_PKG_DIR
    if not base.is_dir():
        return []
    return sorted(
        entry.name
        for entry in base.iterdir()
        if entry.is_dir() and (entry / _MANIFEST_FILENAME).is_file()
    )
