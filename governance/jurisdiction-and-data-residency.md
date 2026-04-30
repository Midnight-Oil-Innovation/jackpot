# JACKPOT — Jurisdiction and Data Residency

## The project's own jurisdiction

The JACKPOT software project is hosted under the
`Midnight-Oil-Innovation/jackpot` GitHub organization. The maintainer entity
(Midnight-Oil-Innovation) is registered in the United States. The canonical
source code, the issue tracker, and the project-side documentation
therefore live under U.S. jurisdiction and U.S. trade-control law.

The project does not host operator data. The maintainer's reference
deployment — used for project testing and demonstration only — runs on
GCP `us-central1` and contains synthetic samples only. No operator's
real-world samples land in any infrastructure operated by the project.

## Operator data lives where the operator runs

JACKPOT is designed so that an operator's pathogen-sequencing data and
metadata stay inside the operator's infrastructure. The platform supports
seven install scenarios (A–F + T — see `spec.md §1`); none of them route
operator data through any maintainer-controlled service.

| Scenario | Data location |
|---|---|
| A — Single academic lab on a laptop | The laptop. |
| B — Single org on cloud | The org's own GCP/AWS/Azure tenancy. |
| C — Multi-lab agency | The agency's IT estate (often state-managed cloud or on-prem). |
| D — Hosted multi-tenant SaaS | The SaaS-host's cloud, governed by their tenancy contract — *not* the JACKPOT project. |
| E — Federation member | The member's own cloud; federation is signed-message exchange between peers, not centralized storage. |
| F — CI / e2e test harness | Ephemeral CI runner; no persistent operator data. |
| T — Tribal-sovereignty deployment | The Tribal authority's own infrastructure, with sovereignty-aware defaults (no auto-publish, deletion-on-request, federation off-by-default). |

The maintainer never has read access to any operator's database or storage
unless the operator explicitly grants it for support purposes. Even then,
the project recommends the operator give read access to a temporary,
auditable account scoped to the issue under investigation, and revoke it
when the issue is closed.

## Applicable law for operators

Operators choosing where to deploy JACKPOT should evaluate:

- **HIPAA / state health-data laws** if any sample metadata could be
  linked back to an individual. JACKPOT's DLP gate (see
  `docs/CLAUDE.md` Critical Rule 43) is a defense-in-depth measure but
  does not by itself constitute HIPAA compliance.
- **Tribal data-sovereignty laws** for Scenario T deployments (e.g.,
  Navajo Nation Human Research Code, IRB-equivalent processes for the
  serving Tribe). The CARE-Principles document and the Scenario T
  defaults exist to make this easier, not to substitute for the
  operator's own legal review.
- **EU GDPR** if any operator's samples touch EU data subjects, even
  transitively.
- **Country-of-collection sovereignty regulations** (e.g., the Nagoya
  Protocol for biological materials with associated traditional
  knowledge). These travel with the sample, not with the platform.
- **Export-control law** for sequence data on dual-use organisms.

The project provides tooling and defaults that make operator-side
compliance easier; the project does not, and cannot, take legal
responsibility for operator-side compliance decisions.

## Federation and cross-jurisdiction sharing

When two or more JACKPOT instances peer with each other (Scenario E),
the federation protocol is signed-message exchange. Each peer's
infrastructure remains within its own jurisdiction; what crosses the
boundary is metadata and sequence references, not storage objects, and
only with explicit per-sample sharing-level configuration on each side.

A federation member can refuse to peer with another instance for any
reason (jurisdictional, governance, technical, or just organizational
preference). The federation protocol does not include a "discoverable by
default" mode.

For Scenario T: federation is OFF by default. A Tribal-sovereignty
deployment can opt in to federation if the Tribal authority decides to,
and federation-aware deletion (see `governance/care-principles-and-
tribal-data-sovereignty.md`) ensures that a deletion request at the home
instance propagates to peers as a deletion command.

## Source-code residency

The canonical source repository is hosted on GitHub. Forks are encouraged
under the AGPL-3.0 terms — operators are welcome to mirror the source
into their own jurisdiction's git infrastructure (Bitbucket Server, GitLab
self-hosted, internal Gitea, air-gapped tarballs distributed via secure
courier). The project commits to making such mirroring straightforward:
no GitHub-specific dependencies in the build, no license-key tokens, no
phone-home telemetry.

## Project-side data

The project itself collects:

- Public GitHub activity (issues, PRs, discussions). Public.
- Commits and code attribution. Public via git history.
- Anonymous web analytics on the project website (forthcoming) using
  privacy-preserving analytics (no cookies, IP truncation).

The project does not collect:

- Operator deployment telemetry. JACKPOT installations do not phone home
  to the project. There is no "register your install" flow.
- User-identifying information from any operator's instance.
- Sequence data, metadata, or pipeline results from any deployment.

If the project ever changes any of the above, the change will be
announced in advance via a public RFC, the change will be opt-in only,
and the privacy-impact analysis will be published in this document.
