# EPISTORM integration

The chat designed a Phase 35 epidemic-modeling integration around epydemix, WhiteLabRt, RtEval, and the EPISTORM software stack. **None of it is in `todo.md`.** This entire section is net-new design work that would need a `jackpot_epidemic_modeling_design.md` anchor document and a fresh round of `B-EPY-*` backlog items before any of it ships.

That said, the design exploration is sound and re-usable. If epi modeling becomes a real priority, here's what was developed.

## Status reality

Grep results across `todo.md`, `spec.md`, `jackpot_session_summary_and_backlog.md`:

- "EPY" → no matches except generic "epidemiology" mentions
- "epydemix" → no matches
- "WhiteLabRt" → no matches
- "EPISTORM" → no matches

The chat's `EPY-S1..S3` schema items + `EPY-1..22` implementation items + Phase 35 + Phase 26 subsection O are phantom. They exist only in the chat transcript.

The closest existing work in JACKPOT that touches forecasting/modeling: Phase IM-2 (Multi-Modal Danger Fusion + DCA in Practice, Tracked Not Scheduled). The BioDendriticCell engine (`B-IMMUNE-DCA-1`) fuses anomaly scores with multi-modal danger signals — that's complementary to but distinct from epidemic modeling. Epi modeling is forward simulation + Rt estimation + scenario exploration; DCA is real-time priority scoring on submitted samples.

## The tools surveyed (still useful as reference)

| Tool | Owner | License | Conceptual role |
|---|---|---|---|
| `epydemix` | EPISTORM (Vespignani et al.) | GPL-3.0 | Stochastic compartmental modeling with ABC calibration |
| `epydemix-data` | EPISTORM | GPL-3.0 | Contact matrices, population pyramids, location parameters (400+ locations) |
| `epyScenario` | EPISTORM | GPL-3.0 | Streamlit web app for interactive scenario exploration (hosted at `scenario.epydemix.org`) |
| `EpyForecast` | EPISTORM | GPL-3.0 | Desktop app for forecasting |
| `Epistorm-Mix` | EPISTORM | GPL-3.0 | 2024 US contact survey (matrices already in epydemix-data as `litvinova_2025`) |
| `WhiteLabRt` | Chad Milando (BU Laura White lab) | MIT | Two-step Bayesian back-calculation (Li 2021) + spatial Rt with state flux (Zhou 2021); STAN-based |
| `RtEval` | EPISTORM | GPL-3.0 | Benchmark harness for Rt estimation methods |
| `summRt` | Milando | MIT | Companion package for Rt summary outputs |
| `linelistBayes` | Milando | MIT | Alternative for line-list-flavored Rt estimation |
| `ern` | PHAC | MIT | Alternative Rt method |
| `EpiNow2` | LSHTM | MIT | Established Rt method |

## License compatibility (verified)

All compatible with AGPL-3.0:

- GPL-3.0 → AGPL-3.0 is one-way compatible. AGPL-3.0 includes GPL-3.0 terms plus network-use provision. JACKPOT can incorporate GPL-3.0 code; the combined work distributes under AGPL-3.0.
- MIT → AGPL-3.0 is trivially compatible.

License check would be enforced by `scripts/verify_licenses.py` (`B-LICENSE-1`, currently queued in IM-1.A) before any wrapped-tool integration. That item is a required quick-win regardless of immune or epi-modeling work.

## What the design proposed (as reference for a future anchor doc)

Three schema items conceptually parallel to the IM-1 `B-IMMUNE-SCHEMA-1` pattern — sit in Phase 24.5 alongside existing sovereignty + BYOP/eukaryotic lockdowns to land in the same P0b migration:

- **`scenario_interventions` typed table.** What intervention scenario did a simulation assume? Captures `intervention_type` enum (vaccination / mask_mandate / school_closure / travel_restriction / nonpharm_other), start/end dates, effectiveness estimate with CI, compliance estimate. FK to a hypothetical `inference_runs` table — but `inference_runs` doesn't exist in real schema either, so this layer too is net-new.
- **`epidemic_forecasts` typed table.** Standardized quantile forecast format compatible with COVID-19 Forecast Hub format. Columns for `model_id`, `target_geography_id`, `target_disease_id`, `forecast_date`, `target_date`, `target_metric` enum, `quantile`, `value`, `forecast_horizon_days`.
- **`rt_estimates` typed table.** `wastewater_sample_id` FK (cross-link to wastewater module if Level 2 ships per `wastewater-roadmap.md`), `rt_method` enum (whitelabrt_li / whitelabrt_zhou / epinow2 / ern / linelistbayes), date, value, CI bounds, effective serial interval, `case_basis` enum.

Implementation items would span ~22 items grouped by layer:

| Layer | Conceptual items |
|---|---|
| Pipelines | epydemix calibration, epydemix simulation, WhiteLabRt Rt estimation |
| Parsers | One per pipeline output |
| Service | Method registry pattern (analogous to `B-IMMUNE-FEAT-1` featurizer registry), benchmark harness |
| API | `/api/v1/epi/scenarios`, `/forecasts`, `/rt` endpoints + RBAC |
| UI | Scenario explorer wireframe + scenario page + forecast viewer + Rt timeline |
| CLI | `jackpot epi ...` subcommands |
| Cross-link | Wastewater-to-Rt linkage (concentration as case-basis input) |
| Tests | Calibration unit tests, ABC convergence, RtEval benchmark integration |
| Docs | Citation tracking, user docs, method-choice rationale |
| Deferred | EpyForecast desktop app integration |

This is roughly 4-6 weeks of focused effort if pursued. Comparable in scope to one of the IM-1.A or IM-2 sub-phases.

## DEC-15 (native vs iframe) — design exploration

Architectural decision the chat explored: whether to integrate epyScenario via iframe (embed the upstream hosted app) or via native reimplementation (rewrite using JACKPOT Streamlit patterns, consuming epydemix as a library directly).

Recommended resolution: **native Streamlit reimplementation.** Reasons:
- Iframe embedding ties JACKPOT to upstream availability + design choices.
- JACKPOT has its own Streamlit UI patterns, authentication, RBAC — iframe bypasses these.
- Native reimplementation keeps the dependency to `epydemix` library only; UI lives in JACKPOT.
- Cost: reimplementation effort. Tracked as wireframe + 3 sub-pages in a hypothetical `B-EPY-*` backlog.

## DEC-16 (default Rt method) — open

Methodological decision: which Rt method is JACKPOT's default? The chat leaned toward WhiteLabRt because its two-step Bayesian back-calculation (Li 2021) is well-suited for the line-list-poor regime JACKPOT often operates in (case counts only, not individual case data). Resolution depends on running RtEval benchmark against representative JACKPOT use cases — which is itself one of the implementation items.

## Coalition value if pursued

Phase 35 was the bridge between JACKPOT's existing genomic surveillance and epidemic modeling / forecasting capability. The Scarpino conversation specifically depends on this being credible.

- **Scarpino (EPISTORM Co-PI)** — adoption of epydemix, citation compliance, NWSS adapter for epydemix as a PR-shaped first contribution. Without epi-modeling integration, the Scarpino conversation is "we'd like to learn from your work" rather than "we're consuming your tools well."
- **Meyers (UT Outbreak Analytics + Disease Modeling Center)** — sister CDC Insight Net center to EPISTORM. Adoption of forecast-hub-compatible output format positions JACKPOT for the Forecast Hub network.
- **Pathak (STPH)** — TPH554 AI/ML in Public Health curriculum maps to epi modeling + anomaly detection together. Scenario explorer is a teaching artifact.
- **Decision Theater (Jin, Wei, Laubichler)** — the Lant 2007 anomaly-detection paper and the Jin et al. 2025 Valley fever LSTM are precedent. JACKPOT-as-substrate for forecasting work positions naturally.

## The honest framing

**Today**, the chat's epi-modeling content is a design starting point, not a tracked deliverable. Translation to real backlog requires (in order):

1. **An anchor design document** — `jackpot_epidemic_modeling_design.md` analogous to `jackpot_immune_platform_plan.md`. Captures the full design (which tools, why, schema, implementation items, success criteria, coalition cross-links). This is 1-2 sessions of design work.
2. **Schema items committed in Phase 24.5** — `B-EPY-SCHEMA-1` for the three typed tables, modeled on `B-IMMUNE-SCHEMA-1`. Lands behind feature flag (`EPI_MODELING_ENABLED=false`) so the migration is safe but no functionality is exposed until the implementation lands.
3. **Implementation items as `B-EPY-*` prefix** under a new phase or under an existing one — Phase IM-2 has the strongest conceptual fit since DCA fusion can consume epi-model outputs.
4. **License compliance check via `B-LICENSE-1`** — the IM-1.A quick-win that needs to land first before any wrapped-tool work. Same prerequisite as immune platform.

Total effort estimate for full Phase 35 if pursued: anchor doc (1-2 sessions) + ~22 implementation items spanning ~4-6 weeks focused work. Roughly the same investment as IM-1.A or IM-2 individually.

## Demo path for laptop Scenario A

If a slim epi-modeling demo is needed before the full Phase 35 commits, the minimum viable cut:

1. **WhiteLabRt-only slice.** R-based via `Rscript`, container built with `rstan` pre-compiled. One Nextflow process; one output parser. Inputs case time series; outputs Rt with CI. Visualizable via a one-page Streamlit add-on.
2. **Synthetic data only.** Use the existing `B-SYNTH-DATA-1` corpus pattern for input. Forecast Hub comparison deferred.
3. **No scenario interventions, no calibration, no forecasting.** Just Rt-from-cases.

That's a ~1-2 week vertical slice. It demonstrates the epi-modeling architectural pattern (R-based pipeline in JACKPOT's existing Nextflow infrastructure, output parsing, Streamlit visualization) without committing to the full epydemix calibration story. It's also enough to anchor the Scarpino conversation about extending into wastewater-driven Rt estimation, which is one of his active grant areas.

## Cross-references for whoever writes the anchor doc

| Source | What it provides |
|---|---|
| EPISTORM `github.com/epistorm/epydemix` | Compartmental modeling library, ABC calibration |
| EPISTORM `github.com/epistorm/epydemix-data` | Contact matrices (mistry_2021, prem_2021, prem_2017, litvinova_2025) |
| Gozzi et al. 2025 *PLoS Comp Bio* 21(11):e1013735 | epydemix methodology paper |
| `github.com/cmilando/WhiteLabRt` | Two-step Bayesian back-calculation, STAN-based |
| Li et al. (referenced in WhiteLabRt docs) | Back-calculation methodology |
| Zhou et al. 2021 | Spatial Rt with state flux |
| `github.com/epistorm/RtEval` | Benchmark harness |
| `reichlab/covid19-forecast-hub` | Quantile-forecast format (archived but canonical) |
| `cdcepi/Flusight-forecast-hub` | Active successor to Forecast Hub |
| Bracher et al. 2021 | WIS metric for forecast evaluation |

These citations are the starting point for the anchor doc. Each tool's upstream README has mandatory citation requirements that the anchor doc must capture (especially `epydemix-data` which explicitly mandates citation of all four contact-matrix sources).
