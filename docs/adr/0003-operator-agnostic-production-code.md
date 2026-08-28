> **Status:** Canonical — architectural decision record.

# Production code carries no operator-specific values

No organization name, email domain, jurisdiction-specific organism list, cloud
project ID, bucket name, endpoint ID, or lab-specific file convention may
appear in production source. Every such value arrives at runtime from one of
three places: environment variables, database tables seeded at install, or
per-deployment operator config files that are never committed.

## Consequences

`jackpot init` is the only component that *learns* operator-specific values —
it prompts for them and writes them into those three sources. This is what
makes a single codebase serve every deployment target, and it is why the
62-value reportable-organism set is a seeded default rather than a constant.
