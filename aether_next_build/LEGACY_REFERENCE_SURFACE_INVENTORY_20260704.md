# Legacy and Reference Surface Inventory

Date: 2026-07-04

Update:
- 2026-07-04 later pass: the compiler `guaranteed_default_ir()` method has
  been deleted from the certified package. The stale replay/debug caller in
  `replay_resume.py` now fails closed with explicit `config_invalid_blockers`
  when a trace config cannot be replay-compiled.

Purpose:
- Identify the remaining non-canonical or legacy-looking surfaces inside
  `aether_next_build/`.
- Distinguish:
  - surfaces that can still affect certified/default execution
  - surfaces that remain only as explicit reference/debug/eval tooling

## Executive Conclusion

After the certified-path quarantine fixes:

- The **public certified/default run surfaces** now fail closed on reference
  architect modes.
- The **remaining residue is mostly reference/debug/eval debt**, not active
  certified-runtime authority.

So the repo is still not minimal, but the most dangerous interference path is
much smaller than before.

## Bucket A — Certified/default execution surfaces

These are the surfaces that matter most for real task attempts.

### `run_pilot.py`

Status:
- canonical default: `workbench`
- reference modes rejected unless explicitly enabled

Role:
- certified/default public launcher

Disposition:
- **Quarantined**

### `aether_next/run_adapter.py`

Status:
- canonical default: `workbench`
- `ensure_certified_architect_mode(...)` fences `ir` / `contract`

Role:
- local/offline adapter entry

Disposition:
- **Quarantined**

### `aether_next/runners/docker_runner.py`

Status:
- now also fences reference architect modes before task execution

Role:
- direct task runner used by `run_pilot.py`

Disposition:
- **Quarantined**

## Bucket B — Canonical runtime internals that still contain legacy fallback code

These are still in the runtime package, but they are no longer the intended
canonical authority path when workbench mode is used successfully.

### `aether_next/model_hooks.py`

Relevant residues:
- `DEFAULT_VERIFIER_IDENTITY_PROMPT`
- `_safe_fallback_turn()`

Interpretation:
- The remaining fallback turn is a solver-turn parse recovery path, not an
  architect/config fallback.
- The verifier prompt constant is already explicitly labeled
  `[legacy fallback only]`.

Risk:
- **Medium conceptual drag**
- **Lower direct certified-runtime risk** than before, because canonical
  workbench path now requires architect-authored verifier prompts more strongly
  and public entry points no longer quietly choose reference modes.

Disposition:
- **Keep for now, treat as reference/fallback debt**

### `aether_next/compiler.py` / `aether_next/kernel_config.py`

Relevant residue:
- explicit invalid-runtime handling for architect/config failures
- field names such as `fallback_codes` that now mean visible invalid/config
  blockers rather than a safe-default replacement

Interpretation:
- The old safe-default compiler method is gone. Certified architect/config
  failure now fails closed and records blockers.

Risk:
- **Low direct risk**
- remaining risk is naming/conceptual drag from historical `fallback` terms

Disposition:
- **Rename/clean up opportunistically; no active safe-default method remains**

## Bucket C — Replay, debug, and analysis utilities

These should not be confused with the certified runtime even though they still
touch legacy fallback concepts.

### `replay_resume.py`

Residue:
- local replay/debug tool reconstructs a trace config and compiles it outside
  certified task execution

Interpretation:
- replay/debug utility, not certified launch surface; invalid reconstructed
  configs now fail closed instead of fabricating a replacement config

Disposition:
- **Reference/debug only, fail-closed**

### `run_verifier_only_eval.py`

Residue:
- imports `DEFAULT_VERIFIER_IDENTITY_PROMPT`

Interpretation:
- generic verifier-only eval harness, not a certified task runner

Disposition:
- **Eval-only residue**

### `run_trace_verifier_replay_ab.py`

Residue:
- imports `DEFAULT_VERIFIER_IDENTITY_PROMPT`

Interpretation:
- replay/analysis tool, not a canonical runtime path

Disposition:
- **Eval-only residue**

## Practical Reading of the Current State

What is true now:

1. The canonical public/default path is much cleaner.
2. The repo still contains legacy/reference internals.
3. Those internals are now better understood as:
   - fallback/reference debt
   - replay/eval tooling
   - conceptual clutter

What is **not** yet true:

1. The repo is not yet minimal.
2. Legacy/reference logic is not fully deleted.
3. Aether-Next is not yet a one-path-only package.

## Recommendation for the Plan

For the remaining reset plan, treat this as:

```text
Certified-runtime quarantine: substantially done
Repo-wide legacy deletion: not done
```

That means it is reasonable to proceed to the single VM validation run without
pretending the repo cleanup itself is finished.
