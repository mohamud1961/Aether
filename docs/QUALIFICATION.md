# Aether public qualification

This document records the deterministic qualification surface shipped with the public Aether release.

## Current public checks

Run from the repository root:

```bash
python -m pytest -q tests
python tools/check_production_surface.py
```

Verified on the public-release branch on 8 September 2026:

```text
701 passed, 1 skipped in 54.93s
```

The production-surface guard returned `status: VALID` and reported:

- 100 production Python modules under `aether/`;
- console entrypoint `aether = aether.launch:main`;
- Harbor adapter `aether.harbor_agent:AetherHarborAgent`;
- Harbor version lock `0.20.0`;
- 100 benchmark-neutrality task identifiers derived from four frozen evidence sources;
- no production task-name leakage detected by the guard;
- no retired Architect/Workbench production imports or control tokens detected by the guard.

## What this proves

These checks establish that the published production package is internally consistent with the current Aether ownership boundary and that the deterministic public suite is green.

They do **not** prove benchmark superiority, universal reliability, or safety. Live model behaviour, provider behaviour, benchmark environments and external graders remain separate empirical questions.

## Why the neutrality evidence is outside `aether/`

The guard derives its denylist from frozen evidence under `tracking/`. Production Aether does not import those files. This lets the release checker test whether benchmark/task identities leaked into production code without making those identities part of the runtime itself.

## Public/research boundary

The public repository deliberately separates:

- `aether/` — production runtime;
- `tests/` — production-bound deterministic qualification;
- `evidence/` — selected public-safe empirical cases;
- `tracking/` — only the frozen authority artifacts needed for public verification;
- broader internal experiment archives — not automatically published.

A clean test suite is necessary engineering evidence. It is not a substitute for the matched live comparisons proposed in the three-month research programme.
