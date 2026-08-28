> **Status:** Canonical — glossary of JACKPOT domain terms.

# JACKPOT

Pathogen genomics platform for genomic epidemiology, bioinformatics, and
public-health research. This file is the glossary: what each domain term
means, and which synonyms to avoid. It is not a spec and holds no
implementation detail — see `docs/architecture.md` for architecture and
`docs/adr/` for decisions.

Terms are added here when they are resolved, not speculatively.

## Sample lifecycle

**Archive**:
Removal of a sample from working views and default queries. All data is
retained — files, metadata, and results stay exactly where they were.
Reversible.
_Avoid_: delete, soft-delete, remove

**Deletion request**:
A recorded intent to remove a sample's content from the system, typically
on withdrawal of consent. Distinct from archiving: a deletion request
begins a lifecycle that ends in the data being gone.
_Avoid_: deletion, takedown

**Tombstone**:
The state in which a sample's derivative rows are sealed against further
change and the sample is marked as pending content removal. The record
that the sample existed survives; the content has not yet been removed.
_Avoid_: soft-delete, marked-deleted

**Vacuum**:
The physical removal of a sample's content — file objects, result payloads,
cached intermediates. What survives is the audit record that the removal
happened, never the removed content itself. Terminal and irreversible.
_Avoid_: purge, hard-delete, wipe

Archive and deletion are **different operations**, not stages of one
operation. Archiving a sample never satisfies a deletion request. See
[ADR-0013](docs/adr/0013-archive-and-deletion-are-distinct.md) for why the two
were separated.

## File storage

**File reference**:
The record of one distinct piece of file content, identified by its
`content_hash`, not by its location. One file reference may be reachable at
several URIs and may be linked to several samples.
_Avoid_: file, file record

**External**:
Storage state meaning JACKPOT knows where the file is but does not own it.
The operator's copy stays where the operator put it and is read in place.
This is the default on ingest — registering a file does not copy it.
_Avoid_: linked, referenced, remote

**Managed**:
Storage state meaning JACKPOT owns the file's lifecycle and holds the
authoritative copy. Pipeline outputs default to this.
_Avoid_: owned, internal, hosted

**Staged**:
Storage state meaning a temporary copy made to move an input across a
compute boundary. Auto-cleaned after the run plus a retention window.
_Avoid_: cached, temp, scratch

**Broken**:
Storage state meaning a file that was registered is no longer readable at
any known URI, or its size no longer matches what was recorded. Terminal
until an operator intervenes.
_Avoid_: missing, orphaned, dead
