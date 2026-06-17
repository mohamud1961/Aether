# Filesystem Open-Workflow Family

**SNAPSHOT** — code is a verbatim copy from `blocks/` as of 2026-06-16.
These files reference `blocks.*` imports and are not standalone-runnable outside the repo root.

## What this family is

Open-workflow path evidence normalization mechanisms for noisy open-file tasks.
The core problem: tasks require opening a specific file, but the agent receives
path evidence that is noisy, aliased, or partially-qualified, causing it to
target the wrong file or report an incorrect answer.

## Variants

| Variant | File | Role |
|---|---|---|
| `open_workflow_answer_candidate_normalizer` | `code/open_workflow_answer_candidate_normalizer.py` | Normalizes answer candidates before final submission |
| `app_open_workflow_path_evidence_normalizer` | `code/app_open_workflow_path_evidence_normalizer.py` | Normalizes path evidence strings in open-workflow contexts |
| `open_workflow_answer_candidate_dispatch` | `code/open_workflow_answer_candidate_dispatch.py` | Context dispatch layer for answer candidates |

## Phase evidence

Phase 4 single-family closeout (2026-05-18): both routes tested for this family
failed target rows entirely. The root cause identified was wrong target-file pattern
matching combined with stale path state after mutation. No variant was promoted.

Phase 5 family-level diagnostic: no updated run was completed for this family.
The underlying code was nonetheless retained as the best available mechanism for
this failure class.

## Status

No tournament scoreboard exists. No variant has been promoted.
These are candidate mechanisms awaiting a valid eval baseline.
See `variants/harness/decision_history.md` Phase 4 for the full authority audit.
