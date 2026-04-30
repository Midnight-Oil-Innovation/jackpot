# JACKPOT — Platform Shutdown and Data-Portability Plan

## What this document is for

JACKPOT is currently maintained by Midnight-Oil-Innovation. Operators
choosing to deploy JACKPOT in production reasonably ask: "what happens to
me if the project stops?" This document is the answer.

The short answer: nothing happens to your operator instance. JACKPOT does
not phone home, does not require a centralized service, and does not gate
any operational function on a project-controlled component. If
Midnight-Oil-Innovation disappears tomorrow, every running JACKPOT
instance keeps working indefinitely.

The longer answer follows.

## Why this is credible (architecturally)

JACKPOT was designed multi-deployment-target from the pivot in April 2026,
which means:

- **No project-controlled API endpoints** in any operator's dataflow. The
  operator's database, storage, OAuth provider, and pipeline executor are
  all within the operator's infrastructure.
- **No project-issued license keys, tokens, or activation calls.** AGPL
  licensing means everything you need to run is in the source.
- **No mandatory phone-home telemetry.** The project does not collect
  install counts, version pings, or feature-use metrics from operator
  instances.
- **No project-hosted package registry.** Python deps come from PyPI;
  Nextflow plugins come from the operator-configured plugin registry
  (default nf-core); Helm charts come from the operator's configured
  chart repository.
- **No project-managed credentials** to NCBI, GISAID, Pathoplexus, or any
  other downstream destination. Each operator brings their own.

A maintainer disappearance breaks new releases, new features, security
patches, and the canonical documentation. It does not break running
operators.

## What you should do today (proactive operator hygiene)

Even though the architecture protects you, treat this as a practical
checklist any operator should run through within 30 days of going to
production:

1. **Mirror the source.** Pull `Midnight-Oil-Innovation/jackpot` to your
   own git infrastructure (Bitbucket Server, GitLab self-hosted, internal
   Gitea, an internal mirror of GitHub). Pin to a specific tag for
   production use.

2. **Mirror Python deps.** If your environment supports an internal PyPI
   mirror (Artifactory, devpi, GitLab package registry), mirror the
   wheels listed in `uv.lock`. This protects you from a PyPI dep being
   yanked or made restricted.

3. **Mirror container images.** Pull the API image and any pipeline
   container images to your operator's Artifact Registry / ECR /
   internal container registry. Update your Helm values to point at
   the mirrored image references.

4. **Document your operator config.** Write down your `jackpot init`
   answers, your Helm values, your Kubernetes secrets manifest (without
   the secrets themselves — store those in your secret manager). This
   is what a future operator will need to redeploy from scratch.

5. **Practice a restore.** Spin up a parallel staging environment from
   your mirrored source, your mirrored deps, your mirrored images, and
   your operator config. Restore your most-recent database backup into
   it. Confirm `/health` returns green and a known sample's metadata
   round-trips. Do this annually.

6. **Subscribe to the project's security disclosures.** Even if no new
   features land, security patches will continue to flow through the
   project's GitHub releases and a security@... mailing list
   (forthcoming).

## What happens to the canonical project if Midnight-Oil-Innovation steps away

In rough order of preference:

1. **Hand-off to a successor maintainer.** If there is a viable
   maintainer in the community (an operator that has been contributing
   code, an academic group, a public-health organization that wants to
   adopt the project), the project commits to a clean hand-off — repo
   transfer, documentation transfer, advisory-board transfer.

2. **Move under a foundation umbrella.** Software in JACKPOT's space has
   precedent for landing in non-profit foundations (Software Freedom
   Conservancy, Open Source Initiative, Linux Foundation projects,
   regional public-health software collaboratives). If there's no
   single-successor maintainer, this is the next preference.

3. **Archive the canonical repo with a forward-looking pointer.** If
   neither (1) nor (2) materializes within 6 months of the maintainer
   announcing intent to step away, the canonical repo is archived (in
   git terms — the GitHub "archive" flag) with a top-level
   `MAINTENANCE_STATUS.md` pointing to whichever community fork has
   become the de-facto continuation. The project maintainer commits to
   actively help one fork become the de-facto continuation rather than
   leaving the community to fragment.

4. **Pure end-of-life.** If even a community fork doesn't materialize,
   the canonical repo stays archived but readable forever. AGPL-3.0
   doesn't expire, your fork doesn't become invalid, and you can
   continue running the last good release indefinitely.

## What never happens

- The project does not assert ownership over operator data. There is
  nothing for the project to "shut down" on the operator side.
- The project does not have a kill switch. There is no remote-disable
  capability for any operator's running instance.
- The license does not change to non-open-source. AGPL-3.0 is a one-way
  door for the canonical project; if a successor maintainer wanted to
  re-license, they would need consent from every contributor whose
  code remained, which is impractical at any non-trivial age. Forks
  remain AGPL-3.0 too.
- The maintainer commits not to use any "rug-pull" pattern (relicense to
  source-available, transition to a different open-source license
  primarily to monetize, abandon the project to push operators toward
  a hosted commercial alternative).

## Notification expectations

If Midnight-Oil-Innovation announces an intent to wind down active
maintenance, the project commits to:

- 90 days advance notice via:
  - A pinned issue in the canonical repo
  - The release notes of the last actively-supported release
  - A GitHub Discussions post inviting successor maintainers
  - Direct email to the address listed in each known operator's
    `governance/coi-disclosures.md` if any operators have opted into a
    "notify me of project status changes" subscription.

- A final security patch release for the most recent stable major
  version, even if that release is partially complete at the wind-down
  announcement.

- Public, written acknowledgment of any successor that emerges, with
  the maintainer's blessing if and only if the maintainer believes the
  successor is operating in good faith.

## A note on operator continuity

The architectural protections above are necessary but not sufficient. An
operator's continuity also depends on internal capacity: someone on the
operator's team needs to be able to run `uv sync`, redeploy the API
container, and apply Alembic migrations. The project commits to keeping
the operational complexity of running JACKPOT low enough that this
remains a small handful of well-documented commands, not a full-time
DevOps engineer. If the operational complexity ever creeps in a way that
makes single-person operator maintenance impossible, that is a project
bug to be tracked in `todo.md`, not an acceptable state.
