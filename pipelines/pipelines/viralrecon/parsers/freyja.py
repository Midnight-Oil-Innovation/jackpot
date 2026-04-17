"""
viralrecon Freyja parser — thin re-export of the shared Cecret parser.

viralrecon's wastewater mode runs Freyja with the same aggregation
command as Cecret, so the TSV schema is identical.  We import the
Cecret implementation rather than duplicate it.
"""

from pipelines.cecret.parsers.freyja import FreyjaParseError, parse

__all__ = ["FreyjaParseError", "parse"]
