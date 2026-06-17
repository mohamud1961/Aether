# Public Readiness

Status: public-safe command surface

This page is the short path for cold-start validation and smoke execution on
the public reviewer surface. It points CI and local reviewers at the same
commands so the public story stays runnable and easy to verify.

## Commands

- `make public-cold-start` runs the public provenance wording sweep and the
  launch-integrity preflight.
- `make public-smoke` runs the synthetic public manifest repair smoke pack.
- `make public-tests` runs the focused pytest slice for the public-readiness
  scaffolding.
- `make public-readiness` runs the three checks together.

## What This Does Not Do

- It does not run private eval packs.
- It does not require raw traces or historian inbox files.
- It does not claim benchmark-grade readiness for the whole repository.

## Evidence Surfaces

- `README.md`
- `PUBLIC_REVIEWER_GUIDE.md`
- `scripts/public_readiness_cold_start.sh`
- `scripts/public_manifest_repair_smoke.sh`
- `tests/test_public_manifest_repair_smoke.py`
