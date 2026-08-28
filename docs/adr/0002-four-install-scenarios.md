> **Status:** Canonical — architectural decision record.

# Four install scenarios, with federation and sovereignty as runtime configuration

JACKPOT targets four canonical install scenarios — A self-hosted commodity
(laptop through multi-lab agency), B HPC (Apptainer + Slurm + institutional
storage), C single-org cloud (Kubernetes), D CI test — reduced from seven in
the May 2026 consolidation.

Federation membership, hosted-SaaS multi-org tenancy, Indigenous data
sovereignty, and network-denied store-and-forward transport were originally
modelled as their own scenarios. They are now **runtime configurations**
applied to A, B, or C.

## Considered options

Keeping them as install scenarios meant every new cross-cutting capability
minted another scenario, and the install matrix grew faster than the test
matrix could cover it. Collapsing them to runtime policy means one install
path per infrastructure shape, and capability differences are configuration a
deployment can change after install without reinstalling.
