> **Status:** Reference — fill_guardrails/review_patterns knowledge-routing design consumed by the fill/consult scripts.

# Pipeline knowledge routing — `fill_guardrails` + `review_patterns`

**tl;dr.** A new version-controlled file, `docs/pipeline_knowledge.yaml`, holds two bodies of *quality knowledge* keyed by phase: `fill_guardrails` (constraints injected into the fill prompt so the generator stops repeating mistakes) and `review_patterns` (checks injected into multi-model review so consultation catches recurring bug classes). The fill script, the consult step, and a closing `jackpot-propagate` step all read and write this one file. The mechanism that makes the pipeline *learn*: every correction a human makes at review becomes a guardrail or pattern that constrains the next session automatically.

This spec covers the schema, the entry-level companions, and how all three threads consume it. It does not cover the full Python rewrites of the fill/consult scripts; those are the build step after this design is approved.

---

## The two design insights

**1. Quality knowledge is category-level, not entry-level.** The M0 review taught us "a `Principal` has `kind`, not `roles`." That is true for M1, M2, M3, M4, M5, and `ACCESS-SEED` too: every entry in the `access_model_redesign` phase. If guardrails lived on individual entries, that lesson would have to be copy-pasted across every authz entry and would drift the moment one copy was edited. The natural key is the `phase` field every entry already carries, so a guardrail attached to a phase applies to all its entries with zero per-entry annotation. Cross-cutting knowledge lives under a `global` key; genuinely one-off knowledge uses an optional per-entry override.

**2. Convention knowledge moves from code to data.** Today `jackpot_fill_prompt.py`'s `SYSTEM_PROMPT` hardcodes domain assumptions (federation scaffold patterns, a 95% coverage figure, `respx`). Those are exactly the assumptions that bled into the M0 authz fill where they did not belong. Moving them out of the script and into `pipeline_knowledge.yaml` as editable data means the propagation loop (point 3) can refine them without a code change, and the fill for an authz session stops inheriting federation conventions it never asked for. The script keeps only invariant instructions (output format, "fill every TODO", Glen's voice); everything domain-shaped becomes data.

Together these are why the pipeline becomes self-improving rather than static: knowledge is data, keyed where it applies, edited by the loop that learns it.

---

## The new file: `docs/pipeline_knowledge.yaml`

Lives beside `active_backlog.yaml` in `docs/`. Top-level shape:

````yaml
version: 1

fill_guardrails:
  global:                       # injected into EVERY fill
    - rule: "..."
  access_model_redesign:        # injected only when entry.phase == this
    - rule: "..."
  federation_stage_1:
    - rule: "..."

review_patterns:
  global:                       # checked in EVERY multi-model review
    - pattern: "..."
  access_model_redesign:
    - pattern: "..."
````

Two top-level sections, each a map of `phase -> list`, plus reserved always-on keys: `global` (both sections) and `security` (review_patterns — see the Security review block below). The phase keys must match phases used in `active_backlog.yaml` (validation below catches typos). It is fine for a phase to be absent (means nothing has been learned for it yet) — the loader treats a missing phase as an empty list.

### Guardrail item schema

A guardrail is an instruction injected into the fill prompt. Required field `rule`; optional `source` and `origin`:

````yaml
- rule: "Principal has `kind` (HUMAN|PEER_INSTANCE|SERVICE) and `on_behalf_of`; it has NO `roles` field. Roles are presets, demoted out of the engine."
  source: "access_model.md §2.1, §8.1"     # where the ground truth lives (optional)
  origin: "M0 fill review 2026-06-09"       # which session's review surfaced it (optional)
````

`source` lets the filler (and a human) trace a guardrail to the authoritative doc. `origin` is the provenance the propagation loop writes, so a guardrail can later be retired if the underlying doc gets clearer, and so you can see which sessions taught the pipeline what. A bare string is also accepted and coerced to `{rule: <string>}`, so quick additions stay quick.

### Review-pattern item schema

A pattern is a check each review model must perform, on top of the standard `/deepreview` perspectives. Required field `pattern`; optional `rationale` and `origin`:

````yaml
- pattern: "Verify every capability name in the diff exists in the access_model.md §4 catalog; flag invented verbs."
  rationale: "Catalog drift is the recurring authz fill error."   # why this check earns its place
  origin: "M0 review 2026-06-09"
````

---

## Entry-level companions (in `active_backlog.yaml`)

Three optional fields are added to the entry schema. None breaks existing tooling (scripts read only the keys they know).

| Field | Type | Purpose |
|---|---|---|
| `context_anchors` | list of `{file, sections}` | The specific doc spans the filler must read and inject as ground truth for THIS entry. The entry-level companion to phase-level guardrails: M0 anchors on §2/§5/§9, M4 on §7. This is the point-1(a) "feed the filler the real definitions" mechanism. |
| `fill_guardrails_extra` | list of guardrail items | One-off fill constraints beyond the phase set, for a single entry. |
| `review_patterns_extra` | list of pattern items | One-off review checks for a single entry. |

`context_anchors` refines, rather than replaces, the existing `source_of_truth_views` (which lists whole files and may be consumed elsewhere). Example on the M0 entry:

````yaml
  context_anchors:
    - file: docs/access_model.md
      sections: ["2.1", "2.2", "2.3", "5.1", "9.1", "9.2", "9.4"]
````

Section ids are **bare numbers**, not `§`-prefixed. The `§` appears only in *cross-references* inside the docs; the actual headers are `### 2.1 Principal — the *who*` (number, space, title). So the extractor matches `### <id> ` (or `## <id> `) and captures to the next header of the same-or-higher level. (The fill script defensively strips a leading `§` if one slips in, but author anchors as bare ids.)

The division of labor is clean: **entry-level** fields say what THIS entry grounds against and any one-off rules; **phase-level** `pipeline_knowledge.yaml` holds the recurring constraints and checks shared across the phase.

---

## Threading: how each step consumes the structure

A resolver composes `global + phase + entry-extra`. As shipped, the fill side and consult side each have a concrete resolver (the fill side returns flat rule strings ready to inject); the shared shape is:

````python
def resolve_guardrails(knowledge: dict, phase: str, extra) -> list[str]:
    """Compose global + phase + entry-extra fill guardrails into a flat list of
    rule strings (bare strings and {rule: ...} dicts both accepted)."""
    block = (knowledge or {}).get("fill_guardrails", {}) or {}
    merged = list(block.get("global", []) or [])
    merged += list(block.get(phase, []) or [])
    merged += list(extra or [])
    out = []
    for g in merged:
        rule = g if isinstance(g, str) else g.get("rule", "")
        if rule:
            out.append(rule)
    return out
````

The consult side is the same composition over `review_patterns`, returning `{pattern: ...}` items — with one addition: it also includes the always-on **`security`** block. So the two compositions are:

- **fill_guardrails:** `global + phase + entry-extra` (no `security` fill block exists yet; if one is added later, the fill resolver gains it for free).
- **review_patterns:** `global + security + phase + entry-extra` — `security` is a reserved always-on key like `global`, so security checks run on every review regardless of phase.

An unknown phase resolves to the reserved keys only (graceful), and entry-level `fill_guardrails_extra` / `review_patterns_extra` append last.

### Thread A — fill (`jackpot_fill_prompt.py`) — SHIPPED

Two additions to `build_user_message`, both additive:

1. **Inject ground truth (point 1a).** For each `context_anchor`, read the file, extract the named sections (matching `### <id> ` to the next same-or-higher header), and add a block:

   ````
   ## Ground-truth definitions — match these EXACTLY, do not reconstruct from memory
   <!-- from docs/access_model.md -->
   [extracted ### 2.1, ### 2.2, ... text]
   ````

2. **Inject guardrails.** Resolve `fill_guardrails` for `entry.phase` plus `entry.get("fill_guardrails_extra")`, and add:

   ````
   ## Fill guardrails — hard constraints you MUST honor (violations are review-blocking)
   - Principal has `kind` and `on_behalf_of`; NO `roles` field. (access_model.md §2.1)
   - Capability names come from the §4 catalog; do not invent verbs. (access_model.md §4)
   - Build the MINIMUM that satisfies the design doc; do not invent structure it does not name. (ponytail)
   ...
   ````

The `SYSTEM_PROMPT` is simultaneously leaned (point 1b): the hardcoded federation / coverage-figure / `respx` / conftest lines are deleted, leaving only invariant instructions (output format, prompt-quality structure, Glen's voice) plus one line deferring to the injected ground-truth and guardrails. Domain knowledge now lives in the data, versioned and propagated-into.

**Four refinements that landed with the rewrite, worth recording:**
- **Rule-names, not numbers.** The leaned prompt instructs the filler to reference session-discipline rules by *name* ("the state-verification rule"), never a placeholder number — fixing the `(Critical Rule N)` artifact that the old `SYSTEM_PROMPT` produced. The agent reads `CLAUDE.md` at session start and resolves names to current numbers itself.
- **Per-entry `fill_model` (point 1d).** An optional `fill_model` field on a backlog entry overrides the default model, so foundational entries (M0, M2) can use a stronger model and routine ones the cheaper default.
- **Deferred SDK + graceful degradation.** The `anthropic` import is deferred into the API path, so `--estimate-cost` and dry runs work without the SDK; a missing or unparseable `pipeline_knowledge.yaml` warns and proceeds with fewer guardrails rather than failing.
- **Measurement hooks.** The metadata sidecar now records `ground_truth_chars` and `guardrails_applied` alongside `todos_remaining`, so `jackpot_trial_log` can quantify whether grounding reduced post-fill correction effort.

### Thread B — consult (`jackpot-consult`, to be built in point 2)

When reviewing a PR, resolve the phase from the entry (the branch name links PR to entry via `branch_name_template`, or pass `--session` explicitly), then resolve `review_patterns` for that phase. Each model (Claude, Codex, Gemini) receives the standard six-perspective `/deepreview` prompt plus:

````
## Phase-specific checks — perform these in addition to the standard perspectives
- Verify every capability name in the diff exists in the §4 catalog; flag invented verbs.
- Verify Principal/Grant/Resource shapes match §2.1–§2.4 (no `roles`, no `principal_matcher`).
````

A `global` review pattern (the **ponytail delete-list**) also runs on every review: flag any abstraction, field, column, or layer the design doc does not require and propose deleting it — with a carve-out so JACKPOT's genuinely-required architecture (AIS/AMAND, the sovereignty deletion lifecycle, the federation layers, the PII/DLP gates) is never mis-flagged as bloat. This is the review-side complement to the "build the minimum the doc specifies" fill guardrail: the generator is told not to over-build, and the reviewer is told to catch it when it does anyway.

The aggregation pass that consolidates the three models' findings also reports which phase-specific checks fired, so a recurring hit is a candidate for tightening the guardrail (it means the *generator* should have prevented it, not just review).

**Three review stages borrowed from pr-af** (concepts, not its framework), to make consult trustworthy rather than just multi-voiced:

1. **Evidence grounding via AST.** Before surfacing a finding ("capability X isn't in the catalog", "this field shouldn't exist"), extract the actual symbol from the code's AST rather than eyeballing the diff text. A claim that can't be grounded in extracted code is pruned. This is what drives toward zero false positives — the `review_patterns` say *what* to check; AST-grounding makes the check *trustworthy*.
2. **Compound-risk synthesis.** Cluster individually-minor findings across files and ask whether they coalesce into one systemic issue. For JACKPOT this is the dual-AIS thesis applied to review: a sovereignty or auth bug is often the *interaction* of two innocent-looking changes.
3. **Falsifiability gate.** Before a finding is surfaced, actively try to invalidate it (is this safe/intended/mitigated elsewhere?). Only findings that survive are reported. This is the maker/checker split applied recursively to the reviewer itself.

#### AUDIT capability — `jackpot-consult` run read-only over existing code

The same three stages work on a *module or package* as well as a PR diff, which gives the loop a read-only **audit** mode for free. A thin `jackpot-audit <path>` wrapper runs the consult review stages (AST-ground, compound-synthesize, falsify) over existing code instead of a diff, resolving `review_patterns` by the target's phase, and writes a ranked findings report rather than PR comments. Properties that keep it safe and useful:

- **Read-only.** Audit never edits. It produces findings; it does not ship fixes. Autonomous *refactoring* of existing code is deliberately NOT a loop capability — it lacks the forward design-doc to ground against (the code *is* the spec), mutates load-bearing depended-upon code (no dark-launch safety), and floods the review bottleneck with the most review-expensive PRs (behavior-preserving refactors). See the audit-vs-refactor split.
- **Findings feed the backlog, not an auto-fix path.** A worthwhile finding is triaged *by the maintainer* into an `active_backlog.yaml` entry, with a `context_anchor` to whatever spec or invariant it should be fixed against. A finding with no groundable spec becomes a *design* task first (write the spec), not a refactor task. The fix then flows through the normal forward loop — bounded session, grounded, single PR, human review.
- **Audit also feeds `review_patterns`.** A finding like "this module invented a precedence column the design doesn't have" is itself a candidate review pattern, so auditing existing code improves the methodology (point 3) at the same time. The codebase audit and the methodology improvement are the same activity.
- **First high-value target:** run `jackpot-audit backend/backend/permissions.py` *before* the M2 cutover, to surface any behavior in the old APGAP ladder the §8.5 preset mapping must preserve — grounding the migration against the real current behavior, not the doc's description of it.

### Thread C — propagate (`jackpot-propagate`, the closing loop)

At session close, after merge, three questions route to three destinations:

| Question | Routes to | Effect |
|---|---|---|
| What did the fill get wrong that review had to fix? | `fill_guardrails[phase]` (append) | next fill in this phase is constrained against the same mistake |
| What did consultation catch that you would have missed? | `review_patterns[phase]` (append) | next review in this phase checks for it explicitly |
| What surprised you about the codebase or design? | `learnings.md` (and the source doc if it is a design fact) | narrative log; doc correction if structural |

This is the step that closes the loop and makes A and B compound. A learning that does not change a guardrail, a pattern, or a doc is just a diary entry; routing each to a destination the pipeline *reads* is what turns review feedback into pipeline improvement. Each appended item gets an `origin` stamp so the provenance is traceable.

---

## Security review block (always-on)

`review_patterns.security` is a reserved always-on block: every `jackpot-consult` run composes `global + security + phase + entry-extra`, so security checks fire on every review regardless of phase. It is seeded from a pre-launch security checklist mapped onto JACKPOT's real stack (FastAPI / raw-SQL PostgreSQL / Google OAuth + JWT / GCP Secret Manager), and it exists because security review is fundamentally an **absence-check** — it looks for *missing* protections (no rate limit, no validation, missing auth), which a correctness review (presence of correctness in a diff) does not do.

The nine seeded patterns and the checklist items they cover:

| Pattern | Checklist item | What it flags |
|---|---|---|
| Rate limiting | 1 | New/expensive/auth routes shipping unthrottled (SEC-2 set the pattern) |
| Server-side validation | 4 | Endpoints consuming user input without a Pydantic model |
| IDOR / cross-tenant access | 5 | By-id fetches or lists not filtered by caller authorization — the primary IDOR surface |
| Write-side authorization | 4/5 | State-changing routes that mutate without a capability check |
| Secrets in code/frontend | 3 | Literal keys/tokens in committed code, incl. Streamlit/built JS |
| Hand-rolled auth/crypto | 8 | Custom crypto/session/token code where OAuth or a vetted library belongs |
| Secrets/PII in logs | (JACKPOT-specific) | Log statements that could emit secrets, federation keys, or un-scrubbed PII/PHI |
| Negative-isolation test | (Guidewire) | Isolation-enforcing changes must ship a test that removes the grant/credential and asserts the request *fails*, not just a positive happy-path test |
| Scope-inheritance by default | (Guidewire) | New child resources (Sample/Project) must inherit the parent scope via a parent-derived `scope_ref`, never an explicit grant a path could forget |

**Two scope boundaries, stated honestly:**

1. **Per-diff review can't answer whole-surface questions.** "Is *every* expensive route rate-limited?" is not answerable from one diff — a diff only shows what changed. Those whole-surface absence sweeps belong to the read-only **AUDIT mode** (`jackpot-audit` over a package, Thread B), not the per-PR consult. The security patterns make a *changed* endpoint get checked; the audit makes the *whole router* get checked. First high-value security audit targets: `backend/backend/routers/` (rate-limit + validation + auth coverage across all endpoints) and `permissions.py` before the M2 cutover.

2. **The IDOR coverage is only as live as the migration.** The strongest coverage (item 5) depends on `permit()` / `visibility_sql_clause`, which are not wired into the live decision path until M2. Until then the live system runs the old APGAP ladder; the security IDOR pattern checks "filter by the caller's authorization" against whatever path is live (the `sample_access` path today, `permit()` after M2). The real IDOR gate is the M2 cutover itself, where the reseed and guard rewrite are where an access-control bug would be introduced — concentrate review there.

### Deliberately NOT in the loop — needs a separate infra checklist

Three checklist items are excluded because they are not code the loop ever sees:

- **Email verification (item 2)** — handled by Google OAuth, not self-serve signup.
- **DB-native RLS / Supabase/Firebase rules (item 6)** — JACKPOT has neither; row protection is enforced at the app tier via `permit()` + `visibility_sql_clause`. (Worth noting the tradeoff: no second-layer DB safety net if the app-tier filter has a bug.)
- **HTTPS / TLS ≥ 1.2 / SPF / DMARC / DNSSEC (item 7)** — deployment/infra settings in Terraform / GKE / the operator's DNS and email domain, structurally invisible to a code-review loop.

> **TODO — scope a per-deployment-scenario infra security checklist.** Items 6 and 7 (and any other deploy-time hardening: secret rotation, network policy, LUKS/disk encryption, bucket ACLs, audit-log retention) live in infra config, not the codebase, and differ by scenario — a Scenario A laptop, a Scenario D hosted SaaS, a Scenario T Tribal-sovereignty deployment, and a Scenario R rural/air-gapped box have materially different infra threat surfaces. This is a separate deliverable from the code-review loop and should be scoped as its own document when a deployment scenario approaches production. The loop covers code; this checklist covers the ground the loop stands on.

---

## Worked example — seeding from the M0 review

The corrections from the M0 prompt review are not hypothetical; they are the first real entries. Seeded into `pipeline_knowledge.yaml`:

````yaml
fill_guardrails:
  global:
    - rule: "Python and Bash only. No other languages. No placeholder code — full implementations always."
    - rule: "File edits via Python scripts using str.replace() with an assert count == 1 guard; never sed. Write to /tmp first, then mv."
    - rule: "Every test file includes at least one failure-path test, not only happy path."
    - rule: "Out-of-Scope items use the 'X (because Y)' pattern so the reason is explicit."
    - rule: "Do not assume conventions from other domains (federation scaffolds, respx, AISHooks, fixed coverage figures) unless the entry's notes or guardrails state them."

  access_model_redesign:
    - rule: "Principal has `kind` (HUMAN|PEER_INSTANCE|SERVICE) and `on_behalf_of`; it has NO `roles` field. Roles are presets, demoted out of the engine."
      source: "access_model.md §2.1, §8.1"
      origin: "M0 fill review"
    - rule: "CapabilityGrant is capability + scope_ref + conditions + source. There is no `principal_matcher`; grants are held by a principal (principal.grants), not matched to one."
      source: "access_model.md §2.2"
      origin: "M0 fill review"
    - rule: "Capability names are `domain:action` strings from the §4 catalog (sample:read_detail, sample:read_surveillance, compute:he_aggregate). Do NOT invent verbs like sequence:read or compute:run."
      source: "access_model.md §4"
      origin: "M0 fill review"
    - rule: "permit() has a structural scope-containment step (step 3: capability granted at a scope that CONTAINS the resource's scope) AND a separate policy step. Strict deny-wins. Do not collapse them into one 'collect ALLOW grants' pass."
      source: "access_model.md §5.1, §5.4"
      origin: "M0 fill review"

review_patterns:
  access_model_redesign:
    - pattern: "Verify every capability name in the diff exists in the access_model.md §4 catalog; flag invented verbs."
      rationale: "Catalog drift is the recurring authz fill error."
      origin: "M0 review"
    - pattern: "Verify Principal/Grant/Resource shapes match §2.1–§2.4 exactly — no `roles` field, no `principal_matcher`."
      origin: "M0 review"
````

Note what this demonstrates: the 30-minute corrective pass we did on `m0-filled-corrected.md` becomes, in this structure, five guardrails the filler will honor on M1 through M5 automatically. The review that cost real time once pays forward across every remaining authz entry. That is the compounding the structure exists to produce.

---

## Validation — extend `jackpot-backlog-check`

A companion check (or an extension of the existing validator) enforces:

1. Every phase key in `pipeline_knowledge.yaml` other than the reserved always-on keys (`global`, and `security` in review_patterns) matches a phase present in `active_backlog.yaml`. Catches typos that would silently no-op a whole guardrail block.
2. Every guardrail has a `rule`; every pattern has a `pattern` (after string coercion).
3. `context_anchors` on entries reference files that exist and a parseable section syntax.
4. Warn (not error) if a phase has entries but no guardrails yet — a nudge that the phase has not learned anything, not a failure.

---

## Open decisions

| Decision | Options | Lean |
|---|---|---|
| One knowledge file or two? | single `pipeline_knowledge.yaml` with both sections / separate `fill_guardrails.yaml` + `review_patterns.yaml` | **single** — they are read together by propagate, share the phase key, and change at the same cadence; one file is one sync point |
| Knowledge in `active_backlog.yaml` or its own file? | sibling top-level keys in the backlog / separate file | **separate file** — scheduling knowledge (what runs, in what order) and quality knowledge (how to fill/review well) change at different rates and are consumed by different scripts; keep their lifecycles apart |
| Cross-phase-but-not-global guardrails | duplicate across phases / add `applies_to_phases: [...]` to a guardrail | **defer** — start with global + per-phase + entry-extra; add `applies_to_phases` only if real need emerges (v1 simplicity) |
| Section-extraction for `context_anchors` | exact header match / fuzzy / line ranges | **exact `§N.M` header match** — the doc already uses stable `§` anchors; extract from one `### N.M` (or `## N.`) header to the next |

---

## Build status and sequencing

This routing structure is the foundation, so it landed first. Status as of this revision:

1. ✅ **DONE — `pipeline_knowledge.yaml` seeded** (point 3a). The destinations exist: 8 global + 7 `access_model_redesign` fill guardrails; 3 global + 7 always-on `security` + 4 `access_model_redesign` review patterns. Includes the two ponytail-derived global entries (anti-over-engineering guardrail + delete-list pattern) and the always-on security block (rate-limit, server-side validation, IDOR, write-side auth, secrets-in-code, hand-rolled-crypto, secrets/PII-in-logs). Validator (`jackpot-knowledge-check`, now treating `security` as reserved) and `context_anchors` on all 8 authz entries shipped alongside.
2. ✅ **DONE — fill script grounds and is constrained** (point 1). `jackpot_fill_prompt.py` reads each entry's `context_anchors` (extracting the exact `### N.M` doc sections as ground truth), resolves `fill_guardrails` (global + phase + entry-extra), and runs a leaned `SYSTEM_PROMPT` that defers to both. Plus the four refinements above (rule-names, `fill_model`, deferred SDK / graceful degradation, measurement hooks). Verified end-to-end via `--estimate-cost`; first real fill is the live test.
3. ⬜ **NEXT — `jackpot-consult` reads `review_patterns`** (point 2). Multi-model review (Claude / Codex / Gemini) with the three pr-af-derived stages (AST-grounding, compound-risk synthesis, falsifiability gate) and the read-only AUDIT mode described in Thread B.
4. ⬜ **`jackpot-propagate` closes the loop** (point 3b). The three closing questions write review feedback back into `fill_guardrails` / `review_patterns` / `learnings.md`.
5. ⬜ **`jackpot-spawn`** last — chains gen → fill → worktree → launch, removing the paste step.

Each step writes into the structure the previous one defined, which is why the routing schema came before the script changes that consume it. Steps 1–2 are the parts that attack the prompt-review bottleneck; step 3 attacks the PR/merge bottleneck; step 5 removes the paste step (the smallest of the three costs).
