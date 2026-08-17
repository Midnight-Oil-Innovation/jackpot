# Fix Plan

- Report: `../code_quality_backend_20260805_142334/report.md`
- Flagged files: 127
- With report signals: 58  (no signal beyond the review: 69)
- Distinct files carrying any report signal: 99
- Priority split: P1 10, P2 18, P3 99

Priority rule: **P1** = security-High, or churn crossed with complexity. **P2** = any churn, complexity, maintainability, or security signal. **P3** = flagged by the review only, no corroborating report signal.

Raw signal columns are shown so you can re-sort. `Cx` is the worst radon cyclomatic grade (C-F), `MI` a low maintainability grade (B-F), `Sec` is bandit High/Medium/Low counts, `Words` is how much the review wrote.

## P1 and P2 (fix these first)

| # | Prio | File | Churn | Fixes | Cx | MI | Sec H/M/L | Dead | Types | Bus | Words | Score |
|--:|:--|:--|--:|--:|:-:|:-:|:-:|--:|--:|:-:|--:|--:|
| 1 | P2 | backend/main.py | 28 | 15 | - | - | - | 4 |  |  | 28 | 116.6 |
| 2 | P2 | backend/config.py | 24 | 12 | - | - | 0/1/0 | 11 |  |  | 335 | 104.0 |
| 3 | P2 | backend/audit.py | 23 | 8 | - | - | 0/0/5 | 17 |  |  | 432 | 95.0 |
| 4 | P1 | backend/validator.py | 12 | 8 | F | - | - |  |  |  | 172 | 67.0 |
| 5 | P1 | backend/routers/pipelines.py | 12 | 5 | F | - | - |  |  |  | 508 | 61.0 |
| 6 | P1 | backend/jobs.py | 10 | 4 | C | - | 0/1/0 | 1 | 5 |  | 157 | 52.5 |
| 7 | P1 | backend/routers/ingest.py | 11 | 4 | D | - | - |  |  |  | 455 | 52.0 |
| 8 | P1 | backend/routers/auth.py | 8 | 6 | C | - | - |  |  |  | 320 | 45.0 |
| 9 | P2 | backend/auth/guards.py | 9 | 6 | - | - | - | 1 | 2 |  | 236 | 43.5 |
| 10 | P2 | backend/pagination.py | 9 | 3 | - | - | 0/1/0 | 3 |  |  | 425 | 40.5 |
| 11 | P1 | backend/harmonizer.py | 6 | 4 | C | - | - | 4 |  |  | 294 | 37.0 |
| 12 | P2 | backend/notifications.py | 7 | 4 | - | - | - | 11 |  |  | 250 | 34.0 |
| 13 | P2 | backend/database.py | 6 | 4 | - | - | - | 1 |  | Y | 391 | 30.5 |
| 14 | P2 | backend/auth/oauth.py | 5 | 4 | - | - | 0/0/1 |  |  |  | 491 | 27.0 |
| 15 | P1 | backend/submissions.py | 4 | 3 | C | - | - |  |  |  | 380 | 27.0 |
| 16 | P1 | backend/routers/samples.py | 5 |  | C | - | - |  |  |  | 304 | 24.0 |
| 17 | P1 | backend/template_generator.py | 5 |  | C | - | - |  |  |  | 915 | 24.0 |
| 18 | P2 | backend/storage/factory.py | 4 | 4 | - | - | - |  |  |  | 391 | 23.0 |
| 19 | P2 | backend/pipeline_results_loader.py |  |  | C | - | 0/2/0 | 5 |  |  | 668 | 13.0 |
| 20 | P2 | backend/imports.py |  |  | D | - | 0/1/0 |  |  |  | 244 | 10.0 |
| 21 | P1 | backend/pipeline_config/profile_renderer.py |  |  | - | - | 1/0/0 |  |  |  | 334 | 9.0 |
| 22 | P2 | backend/file_detector.py |  |  | D | - | - | 1 |  |  | 280 | 7.5 |
| 23 | P2 | backend/pipeline_config/compatibility.py |  |  | D | - | - |  |  |  | 342 | 7.0 |
| 24 | P2 | backend/submission_packages.py |  |  | D | - | - |  |  |  | 356 | 7.0 |
| 25 | P2 | backend/pipeline_config/cluster_reachability.py |  |  | - | - | 0/0/3 | 1 |  |  | 632 | 6.5 |
| 26 | P2 | backend/routers/files.py |  |  | C | - | - |  |  |  | 258 | 5.0 |
| 27 | P2 | backend/routers/sample_access.py |  |  | C | - | - |  |  |  | 338 | 5.0 |
| 28 | P2 | backend/routers/dataharmonizer.py |  |  | C | - | - |  |  |  | 36 | 2.7 |

## Full ranking

| # | Prio | File | Churn | Fixes | Cx | MI | Sec H/M/L | Dead | Types | Bus | Words | Score |
|--:|:--|:--|--:|--:|:-:|:-:|:-:|--:|--:|:-:|--:|--:|
| 1 | P2 | backend/main.py | 28 | 15 | - | - | - | 4 |  |  | 28 | 116.6 |
| 2 | P2 | backend/config.py | 24 | 12 | - | - | 0/1/0 | 11 |  |  | 335 | 104.0 |
| 3 | P2 | backend/audit.py | 23 | 8 | - | - | 0/0/5 | 17 |  |  | 432 | 95.0 |
| 4 | P1 | backend/validator.py | 12 | 8 | F | - | - |  |  |  | 172 | 67.0 |
| 5 | P1 | backend/routers/pipelines.py | 12 | 5 | F | - | - |  |  |  | 508 | 61.0 |
| 6 | P1 | backend/jobs.py | 10 | 4 | C | - | 0/1/0 | 1 | 5 |  | 157 | 52.5 |
| 7 | P1 | backend/routers/ingest.py | 11 | 4 | D | - | - |  |  |  | 455 | 52.0 |
| 8 | P1 | backend/routers/auth.py | 8 | 6 | C | - | - |  |  |  | 320 | 45.0 |
| 9 | P2 | backend/auth/guards.py | 9 | 6 | - | - | - | 1 | 2 |  | 236 | 43.5 |
| 10 | P2 | backend/pagination.py | 9 | 3 | - | - | 0/1/0 | 3 |  |  | 425 | 40.5 |
| 11 | P1 | backend/harmonizer.py | 6 | 4 | C | - | - | 4 |  |  | 294 | 37.0 |
| 12 | P2 | backend/notifications.py | 7 | 4 | - | - | - | 11 |  |  | 250 | 34.0 |
| 13 | P2 | backend/database.py | 6 | 4 | - | - | - | 1 |  | Y | 391 | 30.5 |
| 14 | P2 | backend/auth/oauth.py | 5 | 4 | - | - | 0/0/1 |  |  |  | 491 | 27.0 |
| 15 | P1 | backend/submissions.py | 4 | 3 | C | - | - |  |  |  | 380 | 27.0 |
| 16 | P1 | backend/routers/samples.py | 5 |  | C | - | - |  |  |  | 304 | 24.0 |
| 17 | P1 | backend/template_generator.py | 5 |  | C | - | - |  |  |  | 915 | 24.0 |
| 18 | P2 | backend/storage/factory.py | 4 | 4 | - | - | - |  |  |  | 391 | 23.0 |
| 19 | P2 | backend/pipeline_results_loader.py |  |  | C | - | 0/2/0 | 5 |  |  | 668 | 13.0 |
| 20 | P3 | backend/storage/__init__.py |  | 4 | - | - | - |  |  |  | 553 | 11.0 |
| 21 | P3 | backend/federation/client.py |  | 3 | - | - | - | 3 |  |  | 412 | 10.5 |
| 22 | P2 | backend/imports.py |  |  | D | - | 0/1/0 |  |  |  | 244 | 10.0 |
| 23 | P1 | backend/pipeline_config/profile_renderer.py |  |  | - | - | 1/0/0 |  |  |  | 334 | 9.0 |
| 24 | P2 | backend/file_detector.py |  |  | D | - | - | 1 |  |  | 280 | 7.5 |
| 25 | P2 | backend/pipeline_config/compatibility.py |  |  | D | - | - |  |  |  | 342 | 7.0 |
| 26 | P2 | backend/submission_packages.py |  |  | D | - | - |  |  |  | 356 | 7.0 |
| 27 | P2 | backend/pipeline_config/cluster_reachability.py |  |  | - | - | 0/0/3 | 1 |  |  | 632 | 6.5 |
| 28 | P3 | backend/storage/s3.py |  | 3 | - | - | - |  |  |  | 27 | 6.5 |
| 29 | P3 | backend/crypto/_ais_hooks.py |  |  | - | - | - | 26 |  | Y | 373 | 6.0 |
| 30 | P3 | backend/crypto/keys.py |  |  | - | - | - | 6 |  | Y | 637 | 6.0 |
| 31 | P3 | backend/credentials/__init__.py |  |  | - | - | - | 2 |  | Y | 449 | 5.0 |
| 32 | P3 | backend/credentials/test_helpers.py |  |  | - | - | - | 2 |  | Y | 499 | 5.0 |
| 33 | P3 | backend/federation/_ais_hooks.py |  |  | - | - | - | 4 |  |  | 406 | 5.0 |
| 34 | P3 | backend/immune/sec/dp_aggregator.py |  |  | - | - | - | 6 |  |  | 565 | 5.0 |
| 35 | P3 | backend/permissions.py |  |  | - | - | - | 8 |  |  | 366 | 5.0 |
| 36 | P3 | backend/pipeline_schemas/amr.py |  |  | - | - | - | 16 |  |  | 522 | 5.0 |
| 37 | P3 | backend/pipeline_schemas/assembly_qc.py |  |  | - | - | - | 7 |  |  | 924 | 5.0 |
| 38 | P2 | backend/routers/files.py |  |  | C | - | - |  |  |  | 258 | 5.0 |
| 39 | P2 | backend/routers/sample_access.py |  |  | C | - | - |  |  |  | 338 | 5.0 |
| 40 | P3 | backend/crypto/signing.py |  |  | - | - | - | 1 |  | Y | 250 | 4.5 |
| 41 | P3 | backend/federation/access.py |  |  | - | - | - | 3 |  |  | 258 | 4.5 |
| 42 | P3 | backend/federation/push.py |  |  | - | - | - | 3 |  |  | 624 | 4.5 |
| 43 | P3 | backend/pipeline_config/types.py |  |  | - | - | - | 3 |  |  | 285 | 4.5 |
| 44 | P3 | backend/auth/__init__.py |  |  | - | - | - |  |  | Y | 443 | 4.0 |
| 45 | P3 | backend/auth/dependencies.py |  |  | - | - | - |  |  | Y | 490 | 4.0 |
| 46 | P3 | backend/credentials/cache.py |  |  | - | - | - |  |  | Y | 261 | 4.0 |
| 47 | P3 | backend/credentials/facade.py |  |  | - | - | - |  |  | Y | 245 | 4.0 |
| 48 | P3 | backend/credentials/file_backend.py |  |  | - | - | - |  |  | Y | 3977 | 4.0 |
| 49 | P3 | backend/credentials/gcp_backend.py |  |  | - | - | - |  |  | Y | 365 | 4.0 |
| 50 | P3 | backend/crypto/__init__.py |  |  | - | - | - |  |  | Y | 651 | 4.0 |
| 51 | P3 | backend/pipeline_config/profile_validation.py |  |  | - | - | - | 2 |  |  | 405 | 4.0 |
| 52 | P3 | backend/credentials/base.py |  |  | - | - | - |  |  | Y | 143 | 3.9 |
| 53 | P3 | backend/dlp_scanner.py |  |  | - | - | - | 5 |  | Y | 43 | 3.9 |
| 54 | P3 | backend/crypto/crypt4gh.py |  |  | - | - | - | 8 |  | Y | 29 | 3.6 |
| 55 | P3 | backend/federation/policy_checker.py |  |  | - | - | - | 4 |  |  | 56 | 3.1 |
| 56 | P3 | backend/entrypoint.sh |  |  | - | - | - |  |  |  | 717 | 3.0 |
| 57 | P3 | backend/epiweek.py |  |  | - | - | - |  |  |  | 300 | 3.0 |
| 58 | P3 | backend/file_fingerprint.py |  |  | - | - | - |  |  |  | 567 | 3.0 |
| 59 | P3 | backend/immune/sec/__init__.py |  |  | - | - | - |  |  |  | 285 | 3.0 |
| 60 | P3 | backend/ingest_files.py |  |  | - | - | - |  |  |  | 318 | 3.0 |
| 61 | P3 | backend/log_poller.py |  |  | - | - | - |  |  |  | 491 | 3.0 |
| 62 | P3 | backend/logging_config.py |  |  | - | - | - |  |  |  | 265 | 3.0 |
| 63 | P3 | backend/pipeline_config/batch_submitter.py |  |  | - | - | - |  |  |  | 452 | 3.0 |
| 64 | P3 | backend/pipeline_config/groovy_safe.py |  |  | - | - | - |  |  |  | 376 | 3.0 |
| 65 | P3 | backend/pipeline_config/profile_resolver.py |  |  | - | - | - |  |  |  | 263 | 3.0 |
| 66 | P3 | backend/pipeline_schemas/__init__.py |  |  | - | - | - |  |  |  | 463 | 3.0 |
| 67 | P3 | backend/pipeline_schemas/mag_qc.py |  |  | - | - | - |  |  |  | 370 | 3.0 |
| 68 | P3 | backend/pipeline_schemas/taxonomic_profile.py |  |  | - | - | - |  |  |  | 421 | 3.0 |
| 69 | P3 | backend/pipeline_schemas/tb_typing.py |  |  | - | - | - |  |  |  | 411 | 3.0 |
| 70 | P3 | backend/pipeline_schemas/typing_result.py |  |  | - | - | - |  |  |  | 264 | 3.0 |
| 71 | P3 | backend/pipeline_schemas/wastewater.py |  |  | - | - | - |  |  |  | 285 | 3.0 |
| 72 | P3 | backend/privacy/_ais_hooks.py |  |  | - | - | - |  |  |  | 397 | 3.0 |
| 73 | P3 | backend/privacy/budget.py |  |  | - | - | - |  |  |  | 363 | 3.0 |
| 74 | P3 | backend/privacy/coarsening.py |  |  | - | - | - |  |  |  | 345 | 3.0 |
| 75 | P3 | backend/privacy/scrubber.py |  |  | - | - | - |  |  |  | 267 | 3.0 |
| 76 | P3 | backend/rate_limit.py |  |  | - | - | - |  |  |  | 314 | 3.0 |
| 77 | P3 | backend/responses.py |  |  | - | - | - |  |  |  | 257 | 3.0 |
| 78 | P3 | backend/routers/archive_requests.py |  |  | - | - | - |  |  |  | 222 | 3.0 |
| 79 | P3 | backend/routers/dataset_access.py |  |  | - | - | - |  |  |  | 286 | 3.0 |
| 80 | P3 | backend/routers/datasets.py |  |  | - | - | - |  |  |  | 202 | 3.0 |
| 81 | P3 | backend/routers/gisaid.py |  |  | - | - | - |  |  |  | 1138 | 3.0 |
| 82 | P3 | backend/routers/import_mappings.py |  |  | - | - | - |  |  |  | 514 | 3.0 |
| 83 | P3 | backend/routers/imports.py |  |  | - | - | - |  |  |  | 500 | 3.0 |
| 84 | P3 | backend/routers/labs.py |  |  | - | - | - |  |  |  | 446 | 3.0 |
| 85 | P3 | backend/routers/notifications.py |  |  | - | - | - |  |  |  | 411 | 3.0 |
| 86 | P3 | backend/routers/organizations.py |  |  | - | - | - |  |  |  | 211 | 3.0 |
| 87 | P3 | backend/routers/profiles.py |  |  | - | - | - |  |  |  | 708 | 3.0 |
| 88 | P3 | backend/routers/projects.py |  |  | - | - | - |  |  |  | 282 | 3.0 |
| 89 | P3 | backend/routers/saved_searches.py |  |  | - | - | - |  |  |  | 286 | 3.0 |
| 90 | P3 | backend/routers/settings.py |  |  | - | - | - |  |  |  | 476 | 3.0 |
| 91 | P3 | backend/routers/templates.py |  |  | - | - | - |  |  |  | 626 | 3.0 |
| 92 | P3 | backend/routers/tokens.py |  |  | - | - | - |  |  |  | 459 | 3.0 |
| 93 | P3 | backend/routers/users.py |  |  | - | - | - |  |  |  | 379 | 3.0 |
| 94 | P3 | backend/routers/wastewater.py |  |  | - | - | - |  |  |  | 224 | 3.0 |
| 95 | P3 | backend/settings.py |  |  | - | - | - |  |  |  | 646 | 3.0 |
| 96 | P3 | backend/storage/base.py |  |  | - | - | - |  |  |  | 279 | 3.0 |
| 97 | P3 | backend/storage/gcs.py |  |  | - | - | - |  |  |  | 504 | 3.0 |
| 98 | P3 | backend/storage/local.py |  |  | - | - | - |  |  |  | 272 | 3.0 |
| 99 | P3 | backend/storage/settings.py |  |  | - | - | - |  |  |  | 300 | 3.0 |
| 100 | P3 | backend/submission_executors/seqsender.py |  |  | - | - | - |  |  |  | 339 | 3.0 |
| 101 | P3 | backend/wastewater/__init__.py |  |  | - | - | - |  |  |  | 329 | 3.0 |
| 102 | P3 | jackpot-course/build.sh |  |  | - | - | - |  |  |  | 605 | 3.0 |
| 103 | P3 | scripts/new_session_stub.py |  |  | - | - | - |  |  |  | 248 | 3.0 |
| 104 | P3 | scripts/portal_to_tostadas.py |  |  | - | - | - |  |  |  | 494 | 3.0 |
| 105 | P3 | scripts/seed_sequencing_labs.py |  |  | - | - | - |  |  |  | 345 | 3.0 |
| 106 | P3 | scripts/seed_wastewater_demo.py |  |  | - | - | - |  |  |  | 360 | 3.0 |
| 107 | P2 | backend/routers/dataharmonizer.py |  |  | C | - | - |  |  |  | 36 | 2.7 |
| 108 | P3 | backend/federation/models.py |  |  | - | - | - | 30 |  |  | 28 | 2.6 |
| 109 | P3 | backend/routers/ncbi_submissions.py |  |  | - | - | - |  |  |  | 125 | 2.5 |
| 110 | P3 | backend/routers/sequencing_labs.py |  |  | - | - | - |  |  |  | 125 | 2.5 |
| 111 | P3 | scripts/seed_reportable_organisms.py |  |  | - | - | - |  |  |  | 125 | 2.5 |
| 112 | P3 | backend/privacy/__init__.py |  |  | - | - | - |  |  |  | 112 | 2.2 |
| 113 | P3 | backend/credentials/factory.py |  |  | - | - | - |  |  | Y | 36 | 1.7 |
| 114 | P3 | backend/credentials/env_backend.py |  |  | - | - | - |  |  | Y | 26 | 1.5 |
| 115 | P3 | backend/pipeline_config/__init__.py |  |  | - | - | - |  |  |  | 76 | 1.5 |
| 116 | P3 | backend/middleware.py |  |  | - | - | - | 1 |  |  | 26 | 1.0 |
| 117 | P3 | backend/routers/federation.py |  |  | - | - | - |  |  |  | 47 | 0.9 |
| 118 | P3 | backend/routers/__init__.py |  |  | - | - | - |  |  |  | 39 | 0.8 |
| 119 | P3 | backend/pipeline_schemas/nextclade.py |  |  | - | - | - |  |  |  | 37 | 0.7 |
| 120 | P3 | backend/routers/billing.py |  |  | - | - | - |  |  |  | 36 | 0.7 |
| 121 | P3 | backend/storage/exceptions.py |  |  | - | - | - |  |  |  | 34 | 0.7 |
| 122 | P3 | backend/version.py |  |  | - | - | - |  |  |  | 28 | 0.6 |
| 123 | P3 | backend/immune/__init__.py |  |  | - | - | - |  |  |  | 26 | 0.5 |
| 124 | P3 | backend/pipeline_schemas/pangolin.py |  |  | - | - | - |  |  |  | 27 | 0.5 |
| 125 | P3 | backend/routers/domain_whitelist.py |  |  | - | - | - |  |  |  | 26 | 0.5 |
| 126 | P3 | backend/routers/submissions.py |  |  | - | - | - |  |  |  | 27 | 0.5 |
| 127 | P3 | backend/wastewater/mass_balance.py |  |  | - | - | - |  |  |  | 27 | 0.5 |
