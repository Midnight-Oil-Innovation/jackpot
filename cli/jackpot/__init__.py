"""
jackpot — JACKPOT SDK and CLI

SDK usage:
    from jackpot import Session
    session = Session()
    df = session.samples.search(organism="Salmonella enterica")

CLI usage:
    jackpot upload --r1 sample_R1.fastq.gz --r2 sample_R2.fastq.gz --project 42
    jackpot samples list --project 42
"""
from jackpot.sdk.session import Session

__version__ = "0.1.0"
__all__ = ["Session"]
