# Aether-Next Test Suite Manifest v1

Baseline commit: `0cbefbb47fc185baebfca7ceb41101b033554a2b`
Local platform observed: macOS gateway worktree, Python 3.14

## Declared suites

### S1: Canonical current-package deterministic suite

Command:

```text
python3 -m pytest -q aether_next_build/tests --ignore=aether_next_build/tests/v5_ported
```

Observed local result on 2026-07-20:

```text
556 passed, 16 skipped
```

This is the current reproducible package suite used as the pre-change baseline.
The 16 skips are environment/dependency-conditioned and must be enumerated before
final promotion.

### S2: Full collected tree including V5-ported tests

Command:

```text
python3 -m pytest -q aether_next_build/tests
```

Observed local result on 2026-07-20:

```text
collection failed with 13 import errors
```

Missing exported APIs include `ConfigCompileError`, `EvidenceRecord`,
`ProcessRegistry`, `FIXED_KERNEL_TOOLS`, and `compile_workbench_config`.

Therefore the full test tree is not green and must not be represented as such.
The V5-ported directory is currently migration/reference coverage, not a passing
production suite.

### S3: Previously reported VM result

An exact gateway VM run associated with the `0cbefbb4` proof-contract package
reported:

```text
568 passed, 4 skipped
```

This is not numerically comparable to S1 until its exact command, Python version,
optional dependencies, path, exclusions, and source manifest are retained in one
closure record. The discrepancy is treated as unresolved provenance, not as a
better headline count.

## Certification rules

- Every result must state source commit/tree, clean status, command, working
  directory, Python/platform, exclusions, dependencies, and skip reasons.
- A suite with collection failures is failed, regardless of other passing files.
- Skipped tests cannot cover a mandatory production invariant at 100/100.
- Historical test counts are evidence only for their exact source and command.
- Final certification uses one declared local suite and one declared fresh-VM
  suite against matching source manifests.

## Required future suites

1. Frozen scorecard invariant unit/adversarial tests.
2. Production-path integration suite through the canonical Docker runner/kernel.
3. Provider raw-response fixture replay suite.
4. Security/isolation adversarial suite.
5. Long-run context-growth and evidence-retention suite.
6. Fresh VM parity suite.

## Baseline verdict

Current deterministic core: PASS for S1.
Full repository test tree: FAIL for S2.
VM parity: UNVERIFIED pending exact reconciliation.
Overall test certification: NOT READY.
