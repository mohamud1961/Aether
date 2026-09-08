# Frozen verification authorities

This directory is **not a current product or development surface**.

It contains the small set of historical/frozen authority files that the public release needs in order to verify present-day claims without importing private benchmark archives or rewriting evidence after the fact.

The current production runtime lives in [`../aether/`](../aether/). Current tests live in [`../tests/`](../tests/). Promoted public evidence lives in [`../evidence/`](../evidence/).

## Why this directory exists

Some public checks need an external-to-production authority. For example, `tools/check_production_surface.py` derives a benchmark-task denylist from frozen historical selection/evaluation artifacts and then scans the current `aether/` package to prove those task identifiers did not leak into production code.

Those frozen authorities must stay outside `aether/`; otherwise the checker would make benchmark identities part of the runtime it is trying to audit.

## What is here

- `collab/` — frozen evidence/selection authorities retained for public verification.
- `handoffs/` — historical transition/provenance material retained only where it is part of the public evidence chain.

## Authority rule

Do **not** infer current Aether architecture from this directory.

For current behaviour, use this order:

1. [`../aether/`](../aether/) — current production implementation;
2. [`../tests/`](../tests/) + [`../tools/check_production_surface.py`](../tools/check_production_surface.py) — current deterministic verification;
3. [`../evidence/`](../evidence/) — promoted empirical evidence;
4. [`../docs/`](../docs/) — current documentation;
5. `tracking/` and `research/` — provenance/history only.

Changing a frozen authority solely to make a checker pass would defeat the purpose of the public evidence chain.
