# RAW_LEDGER_UPDATE — Aether-2 fake-progress, W4.1 wiring + collection fixes

Date: 2026-06-15
Plan: `tracking/collab/aether2_fake_progress_implementation_plan_20260614/IMPLEMENTATION_FIX_PLAN.md`

## Status investigation result

On inspection, most of the requested scope was already implemented in the
working tree prior to this session:

- W1.2 (model-visible evidence question / passive reflection) is implemented
  in `runner/aether2/loop.py` `_build_completion_contract` (current_unresolved_requirement,
  strongest_missing_evidence, current_evidence_is_self_authored_or_weak fields,
  `_SELF_AUTHORED_PROVENANCE_LABELS`).
- W2.1/W2.2 ledger progress + provenance machinery (`_ledger_progress`,
  `_new_independent_provenance_added`, `_INDEPENDENT_PROVENANCE_LABELS`) already present.
- W5.3 blocker provenance fields (`required_next_evidence`,
  `rejected_evidence_provenance`, `mark_blockers_candidate_resolved`) already present
  in `runner/aether2/delta.py`.
- The 3 "pre-existing red tests" named in the prompt
  (`test_tool_schema_names_are_exact_and_stable`,
  `test_run_task_via_harbor_raises_on_incomplete_sync_back`,
  `test_run_task_via_harbor_ignores_hidden_workspace_files_when_validating_sync_back`)
  were **already passing** at session start — `task_blocked` tool and
  `bridge_harbor.py` sync-back loud-failure (W9.1) were already implemented.

## Work done this session

### W4.1 — wire `record_terminal_claim` into loop.py (DONE)

- `runner/aether2/loop.py`: imported `record_terminal_claim` from
  `runner.aether2.delta`; in `_execute_tool_calls`, after
  `record_observation_evidence` updates the ledger, for `tool_name in
  {"task_done", "task_blocked"}` the ledger is passed through
  `record_terminal_claim(updated_ledger, claim=arguments, outcome=tool_name,
  step=step, raw_log_path=envelope.raw_log_path)` before being stored via
  `with_evidence_ledger`. `task_done` remains model-callable with no new
  required fields (the existing optional `requirements`/`limitations` fields
  in the tool schema flow straight through to `_normalize_terminal_claim`).

- New homolog test:
  `tests/test_aether2_loop.py::test_circular_task_done_claim_is_recorded_as_weak_terminal_claim`
  — drives the loop through `write_file` then `task_done` with only a
  `cat out.txt` check (circular/self-authored readback, no requirement-evidence
  mapping). Asserts the resulting `post_step_evidence_ledger["terminal_claims"][-1]`
  has `claim_kind == "completion"`, `mapping_status == "weak"`, and
  `requirements == []` — i.e. recorded as weak/unresolved, not promoted to a
  structured claim. Failed before the wiring (empty `terminal_claims`), passes after.

### Test-collection fix (unblocks jobs/metrics suites)

- `tests/test_aether2_jobs.py`: the `verify_stub` module (used to avoid a
  heavier import chain) was missing `RequirementResult`, which
  `runner/aether2/loop.py` imports from `runner.aether2.verify`. This caused
  a collection-time `ImportError` for `tests/test_aether2_jobs.py` and
  `tests/test_aether2_metrics.py` (pre-existing, unrelated to this session's
  loop.py edit — reproduced on a clean stash too). Added
  `verify_stub.RequirementResult = object` alongside the existing stub
  attributes. Both files now collect and pass.

## Test/genericity output

- `tests/test_aether2_loop.py`: 29 passed (28 + 1 new homolog)
- `tests/test_aether2_delta.py`, `tests/test_aether2_verify.py`,
  `tests/test_aether2_tools.py`, `tests/test_aether2_bridge_harbor.py`:
  combined with loop = 75 passed
- `tests/test_aether2_fake_progress_homologs.py`: 3 passed
- `tests/test_aether2_compactor.py` + context + decision_trace +
  entrypoint_import_hygiene + envelope + executor + genericity +
  grader_isolation: 47 passed
- `tests/test_aether2_jobs.py` + `tests/test_aether2_metrics.py`: 11 passed
  (previously: collection error)
- `tests/test_aether2_mirror.py` + model_client + orientation + prompts +
  receipts + sessions: 39 passed
- `tests/test_aether2_targeted_board.py` + vm_lifecycle_scripts: 6 passed
- `tests/test_run_aether2_g2.py`: 19 passed
- `tests/test_run_aether2_g3_official.py`: 5 passed
- `tests/test_run_aether2_tournament.py`: 5 passed

Total across all `tests/test_aether2_*` + `tests/test_run_aether2_*`:
**29 + 46 (delta/verify/tools/bridge) + 3 + 47 + 11 + 39 + 6 + 19 + 5 + 5 = 210 passed**
(29 loop + 24 [delta+verify+tools+bridge already counted earlier as 24 of the
74-set excluding loop] -- see raw numbers above per-file; no failures, no
collection errors across the full `test_aether2_*`/`test_run_aether2_*` set).

`python3 tools/aether2_genericity_check.py` exit code: 0 (after the
loop.py change and after the full session).

## Remaining scope (NOT done this session)

- **W5.2** constraint/final-state coverage in `runner/aether2/verify.py`
  (uncovered declared constraints/required final state as unresolved gaps,
  shape-only/proxy-constraint homolog) — not started.
- **W9.3** scheduler/cleanup truth on the runner path — not started (large
  surface across `tools/run_aether2_g3_official.py` / tournament scripts;
  needs its own homolog + careful no-Docker test design).
- **W10.1** evidence-aware routing/escalation, flag-gated default-off — not
  started.
- Further W5.3 homolog (circular-recovery re-claim stays blocked specifically
  through `record_terminal_claim` + blocker resolution interaction) — the
  underlying blocker-resolution provenance machinery exists but a dedicated
  homolog tying it to the new terminal-claim wiring was not added.

## Guardrails honored

- No model/Docker/VM/board runs executed.
- No commits made.
- `task_done` remains model-callable; no new required fields; `task_blocked`
  already present and unchanged in schema.
- `runner/aether2/` genericity check passes (exit 0) after every change.
