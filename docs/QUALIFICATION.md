# Aether public qualification

[![Public qualification](https://github.com/mohamud1961/Aether/actions/workflows/public-qualification.yml/badge.svg?branch=master)](https://github.com/mohamud1961/Aether/actions/workflows/public-qualification.yml)

This document records the deterministic qualification surface shipped with the public Aether release and the live GitHub qualification that re-runs it from tracked files only.

## Live current-source qualification

Every push and pull request to `master` runs:

```bash
python tools/cold_verify_public_release.py
```

That script copies **tracked files only** into a fresh temporary tree, creates a new Git index, and then runs:

```text
tools/check_public_release.py
tools/check_production_surface.py
pytest -q tests
import aether
```

The first live current-master run on 8 September 2026 completed successfully and reported:

```text
PUBLIC_RELEASE_VALID tracked_files=329 credential_findings=0 sensitive_filenames=0 retired_surfaces=0 current_local_paths=0
production surface: VALID
production Python modules: 100
benchmark-neutrality task identifiers checked: 100
Harbor version: 0.20.0
Harbor adapter: aether.harbor_agent:AetherHarborAgent
console entrypoint: aether = aether.launch:main
701 passed, 1 skipped in 43.58s
AETHER_IMPORT_OK
COLD_PUBLIC_RELEASE_VALID files=329
```

Inspect the stable workflow and its current runs:

[`Public qualification`](https://github.com/mohamud1961/Aether/actions/workflows/public-qualification.yml)

This workflow is intentionally **provider-free**. It does not need private benchmark archives, Azure credentials or model calls.

## Public-release checkpoint

Before the live workflow was added, the public-release branch was also verified on 8 September 2026:

```text
701 passed, 1 skipped in 54.93s
```

That checkpoint is retained as a historical release observation. The live workflow is the stronger current-source proof because it runs outside the development workspace on GitHub's clean runner.

## What the production-surface guard checks

The fail-closed guard scans the current `aether/` package and current package metadata. Among other checks it rejects:

- legacy Aether/HarnessEng runtime imports;
- historical Architect/Workbench cognition modules;
- retired control tokens and runtime selectors;
- checkout-specific local paths;
- hard-coded non-loopback IP addresses;
- benchmark task identifiers derived from frozen external-to-production authorities;
- missing dynamic package dependencies;
- a missing or non-canonical console entrypoint;
- Harbor runtime/version drift;
- launch-schema drift;
- benchmark lifecycle ownership drifting away from Harbor.

On the live run it reported:

- **100** production Python modules under `aether/`;
- console entrypoint `aether = aether.launch:main`;
- Harbor adapter `aether.harbor_agent:AetherHarborAgent`;
- Harbor version lock `0.20.0`;
- **100** benchmark-neutrality task identifiers derived from four frozen evidence sources;
- production-surface status **VALID**.

## What this proves

These checks establish that the published production package is installable, importable and internally consistent with the current Aether ownership boundary on a clean external runner, and that the deterministic public suite is green.

They do **not** prove benchmark superiority, universal reliability, or safety. Live model behaviour, provider behaviour, benchmark environments and external evaluators remain separate empirical questions.

## Why the neutrality evidence is outside `aether/`

The guard derives its denylist from frozen evidence under `tracking/`. Production Aether does not import those files. This lets the release checker test whether benchmark/task identities leaked into production code without making those identities part of the runtime itself.

## Public/research boundary

The public repository deliberately separates:

- `aether/` — production runtime;
- `tests/` — production-bound deterministic qualification;
- `evidence/` — selected public-safe empirical cases and sealed aggregate evidence;
- `tracking/` — only the frozen authority artifacts needed for public verification;
- broader internal experiment archives — not automatically published.

A clean test suite is necessary engineering evidence. It is not a substitute for the matched live comparisons proposed in the three-month research programme.
