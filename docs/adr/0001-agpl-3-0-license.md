> **Status:** Canonical — architectural decision record.

# Use AGPL-3.0, not Apache 2.0

JACKPOT was relicensed from Apache 2.0 to AGPL-3.0 in April 2026. The
motivation is strategic rather than legal: §13 closes the SaaS loophole, so a
hosted operator cannot take the platform private, and it aligns JACKPOT with
the European public-health pathogen-genomics cluster (Loculus,
GenSpectrum/LAPIS, SILO, dashboard-components), all AGPL-3.0.

## Consequences

Direct code adoption from the entire Loculus stack becomes frictionless
(AGPL-3.0 → AGPL-3.0). It also constrains dependencies permanently: anything
carrying BSL, SSPL, or another AGPL-incompatible license is rejected
regardless of technical merit, which is why every new dependency passes
`scripts/verify_licenses.py`.
