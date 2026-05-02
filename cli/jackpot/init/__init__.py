"""
jackpot.init — operator-bootstrap CLI implementation.

Click subcommands live in `cli/jackpot/cli/init.py` and import from this
package for the actual work. This split keeps Click decorators (a heavy
import + framework-coupling) out of the libraries that other tools may
want to use programmatically.

Modules:
- detector  — Click-prompts wrapper around `jackpot_scenarios.detector`
- writers   — emits jackpot.toml, .env.local, values.local.yaml, seed.sql
- secrets   — generates JWT signing key + ed25519 federation keypair
- validator — post-bootstrap /health smoke test
"""
