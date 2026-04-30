"""
nf-core/pathogensurveillance wrapper — pinned at 1.1.0 (M-1, Session M).

pathogensurveillance is the densest parser in the JACKPOT wrapper suite:
one run produces eight result surfaces across four tables.  The spec
pins the pipeline version at 1.1.0 for the prototype — other versions
are accepted by the wrapper but emit a ``pipeline_events`` warning
(enforced by the top-level run launcher, not the parser layer).

Result surfaces (full list in ``spec.md`` §Session M):

* sendsketch identification        → ``taxonomic_profile``
* AMRFinderPlus (shared normalizer) → ``amr_results``
* tseemann ``mlst``                → ``typing_results``
* graphtyper VCF summary            → ``pipeline_metrics``
* per-sample reference selection    → ``pipeline_metrics`` (reproducibility)
* core gene / BUSCO / SNP phylogeny trees → ``sample_files`` (run-level)
* interactive HTML report          → ``sample_files`` (run-level)
"""

from .parsers import SUPPORTED_PIPELINE_VERSIONS, collect_files, parse

__all__ = ["SUPPORTED_PIPELINE_VERSIONS", "collect_files", "parse"]
