"""
nf-core/taxprofiler wrapper — metagenomic taxonomic profiling.

Unlike Grandeur's single-organism Kraken2 use, taxprofiler retains the
full ranked list of taxa per sample.  Each classifier output becomes
one or more :class:`TaxonomicProfile` rows; a DIAMOND protein profile
(when present) becomes a ``pipeline_metrics`` row capturing the
summary stats only.
"""

from .parsers import SUPPORTED_PIPELINE_VERSIONS, collect_files, parse

__all__ = ["SUPPORTED_PIPELINE_VERSIONS", "collect_files", "parse"]
