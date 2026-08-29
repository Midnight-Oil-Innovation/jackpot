> **Status:** Reference — how engineering skills consume this repo's domain docs.

# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, or
- **`CONTEXT-MAP.md`** at the repo root if it exists — it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in. In multi-context repos, also check `src/<context>/docs/adr/` for context-scoped decisions.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

This is a **single-context** repo.

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-....md
│   └── 0002-....md
└── backend/ cli/ schema/ pipelines/
```

For reference, a multi-context repo (signalled by `CONTEXT-MAP.md` at the root) would look like:

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← system-wide decisions
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← context-specific decisions
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

Neither `CONTEXT.md` nor `docs/adr/` exists yet — that's expected. Don't create them preemptively.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Repo-specific sources

Until `CONTEXT.md` exists, treat these as the working glossary and decision record:

- **`docs/domain_reference.md`** — cross-doc glossary plus the source-of-truth map naming which document is canonical for each topic. This is the closest existing equivalent to `CONTEXT.md`; read it first.
- **`docs/architecture.md`** — canonical system architecture. Architectural decisions currently live here in narrative form rather than as numbered ADRs.
- **`CLAUDE.md`** — the Critical Rules are binding constraints, not merely conventions. A proposal that violates one is wrong by construction; treat a conflict the same way you'd treat an ADR conflict below.

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_

The same applies to a contradiction with a Critical Rule in `CLAUDE.md` or a
canonical claim in `docs/architecture.md`: name the rule or section, then argue.
