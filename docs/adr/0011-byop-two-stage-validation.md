> **Status:** Canonical — architectural decision record.

# BYOP pipelines pass two validation stages before activating

Registration runs static checks (manifest schema, engine syntax,
container and reference resolution, license, permissions) followed by a
sandbox dry-run (isolated namespace and network, five-minute timeout,
synthetic inputs). Both must pass. Re-validation runs quarterly to catch
upstream rot.

## Considered options

Static-only lets runtime bugs through. Sandbox-only misses structural problems
that are cheap to catch before spending compute. Requiring Lab Director
approval for every registration would suppress adoption, which defeats the
purpose of BYOP. Two automated stages plus quarterly revalidation was the
balance chosen.
