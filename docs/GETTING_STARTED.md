# Getting started

Aether's public release is designed so the core runtime and deterministic qualification can be inspected without private benchmark archives or provider credentials.

## Requirements

- Python 3.11+
- a virtual environment

Harbor integration is pinned separately to Harbor `0.20.0`.

## Install from a clone

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

At the public-release checkpoint used for funding diligence, this suite reports:

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

## What these checks do not prove

A clean deterministic suite does not prove that Aether is benchmark-competitive or that autonomous model behaviour is generally safe.

For held-out evidence, read:

- [`../evidence/qualification/`](../evidence/qualification/) — the sealed H10 campaign, including weak performance;
- [`../evidence/terminal-bench/configure-git-webserver/`](../evidence/terminal-bench/configure-git-webserver/) — selected capability/attribution case;
- [`../evidence/safety/workspace-boundary-rejection/`](../evidence/safety/workspace-boundary-rejection/) — boundary-held failure case.

## Runtime entrypoint

The package exposes:

```text
aether = aether.launch:main
```

The model/provider path used for live research requires appropriate provider credentials and is intentionally not needed for the public deterministic qualification path.
