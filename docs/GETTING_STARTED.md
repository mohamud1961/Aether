# Getting started

Aether's public release is designed so the current runtime and deterministic qualification can be inspected without private benchmark archives or provider credentials.

## Requirements

- Python 3.11+
- a virtual environment

Harbor integration is pinned separately to Harbor `0.20.0`.

## Clone the current release surface

For ordinary review, use a shallow clone:

```bash
git clone --depth 1 https://github.com/mohamud1961/Aether.git
cd Aether
```

Aether's public Git history is intentionally much larger than the current release surface because it preserves earlier research and development provenance. You do **not** need that full history to install, inspect or qualify the current runtime. Remove `--depth 1` only when you specifically want the historical lineage.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
```

For Harbor integration:

```bash
python -m pip install -e '.[test,harbor]'
```

## Run the public deterministic suite

```bash
python -m pytest -q tests
```

At the current public funding-diligence checkpoint, this suite reports:

```text
701 passed, 1 skipped
```

The skip is preserved rather than silently removed from the count.

## Check the production surface

```bash
python tools/check_production_surface.py
```

The checker is fail-closed. It verifies the current `aether/` package identity, Harbor lock, launch schema and benchmark-neutrality boundary against frozen non-production authorities.

Expected release status:

```text
"status": "VALID"
```

## Inspect the static runtime surface

```bash
python tools/runtime_surface_report.py \
  --json runtime-surface.json \
  --text runtime-surface.txt
```

This parses every tracked production Python module and reports static intra-package import reachability from Aether's canonical public entrypoints. It is a **review aid, not a dead-code oracle**: optional, registry-based or other dynamic loading can be invisible to static analysis.

The public GitHub qualification workflow runs this report on every push and preserves it beside the exact Python/package environment as a per-commit Actions artifact.

## Reproduce the tracked-files-only qualification

```bash
python tools/cold_verify_public_release.py
```

This creates a clean temporary copy from tracked files only, then runs publication hygiene, the production-surface guard, the deterministic suite and an import check. It is the closest local equivalent of the public GitHub Actions qualification job.

## What these checks do not prove

A clean deterministic suite does not prove that Aether is benchmark-competitive or that autonomous model behaviour is generally safe.

For empirical evidence, read:

- [`../evidence/qualification/`](../evidence/qualification/) — the sealed H10 campaign, including weak performance;
- [`../evidence/terminal-bench/configure-git-webserver/`](../evidence/terminal-bench/configure-git-webserver/) — selected capability/attribution case;
- [`../evidence/safety/workspace-boundary-rejection/`](../evidence/safety/workspace-boundary-rejection/) — boundary-held failure case;
- [`EVIDENCE_PIPELINE.md`](EVIDENCE_PIPELINE.md) — what the live runtime records and how evidence is promoted publicly.

## Runtime entrypoint

The package exposes:

```text
aether = aether.launch:main
```

The model/provider path used for live research requires appropriate provider credentials and is intentionally not needed for the public deterministic qualification path.
