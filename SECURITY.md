# Security policy

Aether is a public research agent runtime that executes model-authored actions inside bounded task environments. Security reports about the current runtime are useful, especially when they concern execution boundaries, workspace isolation, evidence integrity, provider credential handling, or publication redaction.

## Reporting a vulnerability

Please send security-sensitive reports directly to:

**mohamud1961@gmail.com**

Please do **not** open a public GitHub issue first if the report includes:

- a credential, token or private endpoint;
- a reproducible escape from an execution/workspace boundary;
- a path to hidden benchmark/evaluation material;
- a way to tamper with or misattribute run evidence;
- unrelated personal/private data exposed by a trace or artifact.

Include enough information to reproduce and scope the issue if it is safe to do so: affected commit/version, environment assumptions, steps, observed result, and expected boundary.

There is currently no formal bug-bounty programme or guaranteed response SLA.

## Supported research surface

Security review should target the current production authority documented in:

- `aether/`;
- `aether = aether.launch:main`;
- `aether.harbor_agent:AetherHarborAgent`;
- `docs/RUNTIME_SURFACE.md`;
- the current `master` qualification workflow.

Historical material under `research/`, frozen `tracking/` authorities and old Git history may contain retired architectures. Findings against those historical surfaces are still useful for provenance, but they should not automatically be interpreted as defects in the current runtime.

## Research/safety claim boundary

Aether's execution controls are research architecture, **not a claim of proven general AI safety**. A boundary bypass, evidence-integrity failure or unsafe default in current production should therefore be reported as an empirical finding rather than treated as contradicting a claimed safety certification that the project does not make.
