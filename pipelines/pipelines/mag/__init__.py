"""
nf-core/mag wrapper — metagenome-assembled genome pipeline.

nf-core/mag emits **one parent metagenomic sample → many MAG bins**.
Each MAG bin is registered as a derived sample by the backend; the
parser layer surfaces:

* :class:`MAGQC` rows (one per bin, ``sample_id`` = parent, ``bin_id`` = bin)
* :class:`TaxonomicProfile` rows from GTDB-Tk (``sample_id`` = bin_id)
* :class:`FileArtifact` rows for every bin FASTA (``sample_id`` = bin_id,
  ``file_subtype='mag_bin'``)

The backend's registration endpoint is responsible for creating derived
sample rows and wiring them to the parent via
``sample_associations(association_type='mag_bin')`` — the parser layer
only emits the raw bin_id / parent_sample_id pair.
"""

from .parsers import SUPPORTED_PIPELINE_VERSIONS, collect_files, parse

__all__ = ["SUPPORTED_PIPELINE_VERSIONS", "collect_files", "parse"]
