# Verifier Repair Family

**SNAPSHOT** — code is a verbatim copy from `blocks/` as of 2026-06-16.
These files reference `blocks.*` imports and are not standalone-runnable outside the repo root.

Note on naming: this family was previously labeled with a benchmark-specific prefix
in the internal working tree. That prefix has been stripped for the public gallery.
The mechanism code itself is generic; it is not specific to any benchmark.

## What this family is

Verifier-episode parser and repair mechanisms for tasks where the grader requires
a re-run of verification after agent edits. The failure mode: agent completes
editing but the verifier exits before the grader can confirm, leaving the task
in a failed state even when the edit was correct.

## Variants

| Variant | File | Role |
|---|---|---|
| `verification_repair_loop_01` | `code/verifier_repair_projection.py` | Path-normalized verifier repair projection (renamed from `path_normalized_verifier_repair_projection.py`) |
| `verifier_episode_parser` | `code/verifier_episode_parser.py` | Parses verifier episode structure for repair targeting |

## Phase evidence

Phase 4 single-family closeout (2026-05-18): both `verification_repair_loop_01`
and `artifact_and_verifier_hard_gate_01` passed all rows — but the eval was
classified as **non-discriminating** (too easy to be a useful diagnostic).
The passing result is not a promotion claim; it confirms the mechanism is
not harmful, not that it is beneficial.

Per the Phase 4 authority audit: "expand homolog pressure before retesting" was
the recommended next step, not promotion.

## Status

No tournament scoreboard exists. No variant has been promoted.
The non-discriminating eval result means Phase 4 data cannot serve as
promotion evidence. A harder or more varied eval surface is required.
See `variants/harness/decision_history.md` Phase 4 for the full authority audit.
