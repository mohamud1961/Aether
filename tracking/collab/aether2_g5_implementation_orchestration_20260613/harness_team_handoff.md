# Harness Team H Handoff

## Final status

`READY_FOR_PARENT_HARNESS_INTEGRATION`

Objective completed:
- Implemented the generic Aether-2 state/ledger/verifier/no-progress/tool-channel/truncation/receipt upgrades in Team H ownership.
- Integrated the new mandatory `Verifier Blocker Persistence` and `Environment Contract And Real Service Monitoring` requirements into the live harness.
- Completed local proof on synthetic/original Aether-2 behavior tests only; no targeted board or real benchmark rows were run.

Scope completed:
- `runner/aether2/*.py` Team H slices, with `runner/aether2/loop.py` integrated only by the lead thread.
- Harness-behavior tests under `tests/test_aether2_*.py`.

Out of scope / untouched by ownership:
- `tools/run_aether2_g3_official.py`
- tournament / safe-run / external grader mounting / targeted-board scheduler surfaces

## Files changed

Primary harness files:
- `runner/aether2/context.py`
- `runner/aether2/compactor.py`
- `runner/aether2/delta.py`
- `runner/aether2/envelope.py`
- `runner/aether2/executor.py`
- `runner/aether2/jobs.py`
- `runner/aether2/loop.py`
- `runner/aether2/mirror.py`
- `runner/aether2/orientation.py`
- `runner/aether2/prompts.py`
- `runner/aether2/receipts.py`
- `runner/aether2/verify.py`

Primary tests touched:
- `tests/test_aether2_bridge_harbor.py`
- `tests/test_aether2_compactor.py`
- `tests/test_aether2_context.py`
- `tests/test_aether2_delta.py`
- `tests/test_aether2_envelope.py`
- `tests/test_aether2_executor.py`
- `tests/test_aether2_jobs.py`
- `tests/test_aether2_loop.py`
- `tests/test_aether2_mirror.py`
- `tests/test_aether2_orientation.py`
- `tests/test_aether2_prompts.py`
- `tests/test_aether2_receipts.py`
- `tests/test_aether2_verify.py`

## Package disposition

H0 characterization: 100%
- Read AGENTS + implementation/execution/failure docs, frozen Attempt 1 evidence, and the architecture transcript before patching.

H1 receipt / input truth: 100%
- Exact normalized model exchange receipts with `call_role`.
- Tail/ledger/tool-schema context captured.
- EnvContract digest/version now captured under `request_context.env_contract`.

H2 top+bottom contract salience: 95%
- Immutable top contract preserved.
- Dynamic completion-contract tail block implemented and fed by live ledger/blocker state.
- Prompt additions are intentionally provisional per orchestrator timing note; keep for current behavior/tests only.

H3 durable evidence ledger + compaction: 100%
- Durable requirement ledger implemented.
- Persistent blocker state machine added with deterministic serialization.
- Compactor preserves ledger + blockers.

H4 evidence-strength classification: 100%
- Generic evidence-strength + confidence + reasons implemented.
- Parse/schema failure remains explicit unresolved evidence.
- Service/persistence heuristics distinguish weak startup/process/port evidence from bounded survival/client/state evidence.

H5 verifier completion semantics: 100%
- `unsatisfied`, `unverifiable`, and parse/schema findings remain unresolved.
- Bounded three-round behavior preserved.
- Repeated `task_done` with unchanged blocker state is pre-rejected without another verifier model call.
- Exhaustion marks blockers honestly and exits unresolved.

H6 semantic no-progress: 100%
- Semantic repeated-strategy detection implemented.
- Legacy identical zero-delta streak note preserved where no semantic failure state exists.

H7 literal tool execution: 100%
- Foreground multiline commands and detached jobs use literal scripts, not eval.

H8 truncation digest: 100%
- Deterministic decisive-middle truncation digest surfaced in tool observations.

H9 interaction/integration behavior: 95%
- Integrated locally in `loop.py` with focused and full tests.
- Local synthetic/original A/B behavior evidence recorded below.
- No targeted board executed, by instruction.

New mandatory tightened-plan items:
- Persistent verifier blocker state: 100%
- EnvContract/substrate mapping: 100%
- Real bounded service monitoring: 90%
  - Implemented bounded monitoring for jobs/sessions/services, start/end survival, PID replacement, log growth/error detection, same-workspace probe classification, timeout/mismatch signals, and summary surfacing into verifier-visible `action_digest.service_monitoring`.
  - Remaining depth belongs to Team R integration on external runner manifests/port allocation/drift classification beyond Team H ownership.

## Team R interface

EnvContract surface:
- Orientation now includes:
  - `env_contract_version`
  - `env_contract_digest`
  - `env_contract`
- `env_contract` sections:
  - `workspace`
  - `paths`
  - `execution`
  - `python`
  - `package_managers`
  - `permissions`
  - `network`
  - `persistence`
  - `services`
  - `runtime`
  - `grader_boundary`
- Unknowns serialize honestly as `{known: false, value: null, basis: [...], note: ...}`.
- Receipts copy `request_context.env_contract.{version,digest}` from the model-visible orientation snapshot automatically.

Blocker surface:
- Ledger root now contains:
  - `version`
  - `requirements`
  - `blockers`
  - `repeated_failure_families`
- Each blocker serializes:
  - `blocker_id`
  - `requirement_id`
  - `requirement`
  - `verdict`
  - `reason_codes`
  - `created_step`
  - `last_updated_step`
  - `age_steps`
  - `rejected_evidence_refs`
  - `insufficiency_reason`
  - `required_next_evidence`
  - `evidence_version_last_evaluated`
  - `status`
  - `resolution_evidence`
  - `verifier_confirmation`
  - `evaluation_rounds`
  - `candidate_resolution_attempts`
- Loop-side suppression uses:
  - `mark_blockers_candidate_resolved(...)`
  - `should_suppress_verifier_call(...)`
  - `mark_blockers_exhausted(..., force=True)` on bounded terminal exhaustion

Service-monitoring surface:
- Verifier-visible `action_digest` now includes:
  - `environment_contract`
  - `service_monitoring`
  - `tool_calls`
- `service_monitoring` shape:
  - `applies`
  - `window_sec`
  - `jobs`
  - `sessions`
  - `services`
  - `summary`
- Summary strings intentionally include generic signals that match the plan:
  - `still running after ... bounded window`
  - `pid changed ...`
  - `client probes ran from the same workspace root`
  - `client probes did not run from the same workspace root`
  - `client probe timed out ...`
  - `repeated client probes returned the same response body ...`

## Subagent handoffs

Completed bounded worker slices:
- H1 receipt/input truth worker:
  - `runner/aether2/receipts.py`, `runner/aether2/context.py`, receipt/context tests
- H3 ledger/compaction worker:
  - initial evidence-ledger/compaction scaffold landed
- H4/H5 verifier semantics worker:
  - `runner/aether2/verify.py`, verifier tests
- H6 no-progress worker:
  - `runner/aether2/mirror.py`, mirror tests
- H7 literal execution worker:
  - `runner/aether2/executor.py`, `runner/aether2/jobs.py`, tests
- H8 truncation digest worker:
  - `runner/aether2/envelope.py`, tests

Second wave:
- EnvContract/receipt worker completed cleanly and was accepted.
- Verifier/service-evidence worker completed cleanly and was accepted.
- Blocker-state worker hit a usage-limit error before formal closeout. The live patch had already landed substantial delta/blocker code, so the lead thread reviewed, repaired two failing blocker behaviors, reran `tests/test_aether2_delta.py`, and completed the integration locally. This should be treated as an accepted-but-lead-finished handoff, not as a clean worker closeout.

## Tests and evidence

Focused suites used during integration:
- `python3 -m pytest tests/test_aether2_receipts.py tests/test_aether2_context.py -q -p no:cacheprovider`
- `python3 -m pytest tests/test_aether2_verify.py tests/test_aether2_delta.py tests/test_aether2_compactor.py tests/test_aether2_mirror.py -q -p no:cacheprovider`
- `python3 -m pytest tests/test_aether2_orientation.py tests/test_aether2_receipts.py -q -p no:cacheprovider`
- `python3 -m pytest tests/test_aether2_prompts.py tests/test_aether2_loop.py -q -p no:cacheprovider`
- `python3 -m pytest tests/test_aether2_loop.py::test_bounded_service_monitoring_reports_survival_same_workspace_and_stable_response tests/test_aether2_loop.py::test_bounded_service_monitoring_reports_crash_and_environment_mismatch tests/test_aether2_loop.py::test_bounded_service_monitoring_reports_service_pid_replacement -q -p no:cacheprovider`
- `python3 -m pytest tests/test_aether2_loop.py::test_repeated_task_done_with_unchanged_blockers_suppresses_second_verifier_call tests/test_aether2_loop.py::test_verification_action_digest_surfaces_env_contract_drift -q -p no:cacheprovider`

Required final local gates:
- `python3 -m pytest tests/test_aether2_*.py -q -p no:cacheprovider`
  - run 1: `163 passed in 81.31s`
  - run 2: `163 passed in 77.10s`
  - run 3: `163 passed in 135.67s`
- `python3 -m py_compile runner/aether2/*.py tools/run_aether2_g2.py`
  - passed on final state
- `python3 tools/aether2_genericity_check.py`
  - passed on final state

A/B interaction evidence used locally (synthetic/original behavior runs only):
- `ledger only`
  - evidence: `tests/test_aether2_delta.py`
  - result: blocker persistence, aging, suppression precheck, candidate resolution, exhaustion all green
- `evidence only`
  - evidence: `tests/test_aether2_verify.py`
  - result: weak/strong evidence classification, parse/schema unresolved truth, service startup-only vs bounded survival/client/state signals all green
- `ledger + evidence`
  - evidence: combined `tests/test_aether2_delta.py tests/test_aether2_verify.py`
  - result: compatible and green
- `verifier only`
  - evidence: `tests/test_aether2_loop.py::test_loop_terminates_on_task_done_and_runs_finalize`
  - result: completion verification path green
- `ledger + verifier`
  - evidence: `tests/test_aether2_loop.py::test_repeated_task_done_with_unchanged_blockers_suppresses_second_verifier_call`
  - result: second verifier call suppressed; unresolved truth preserved
- `no-progress only`
  - evidence: `tests/test_aether2_mirror.py` and `tests/test_aether2_loop.py::test_mirror_note_after_three_identical_zero_delta_actions`
  - result: semantic and legacy no-progress paths both green
- `all mechanisms together`
  - evidence: three consecutive full `tests/test_aether2_*.py` passes
  - result: green on full local Aether-2 suite
- `tool cleanup alone and combined`
  - evidence: `tests/test_aether2_executor.py tests/test_aether2_jobs.py tests/test_aether2_envelope.py` and full suite
  - result: green

## Review gate

Requested gate:
- `codex_review_skill_plus_adversarial`

Codex review helper attempt:
- command: `~/.codex/skills/codex-review/scripts/codex-review --mode auto`
- result: failed before review execution
- exact failure:
  - `Error loading config.toml: unknown variant 'default', expected 'fast' or 'flex' in service_tier`

Fallback performed:
- source-level self-review over the live dirty tree
- adversarial pass against AGENTS.md, IMPLEMENTATION_PLAN.md, genericity constraints, and the valid Attempt 1 failure themes

Accepted findings repaired:
- test helpers still emitted pre-schema verifier payloads without `evidence_refs`
- resolved requirements still retained old blocker summaries in one blocker path
- repeated failed checks were incorrectly treated as new blocker-relevant evidence in loop suppression
- legacy zero-delta mirror note was masked by the semantic path
- job-survival regression test used `sleep 5`, which became too short after added verification/orientation overhead

Rejected / deferred findings:
- none on correctness
- prompt redesign beyond the small current additions is explicitly deferred by orchestrator instruction

## Residual risks and exact next action

Residual risks:
- Team R still needs to decide whether the new `env_contract` serialization is the exact shared long-term substrate schema or whether field naming should be normalized before official runner/result-row adoption.
- Service monitoring is intentionally bounded and generic. It does not invent hidden runner/container knowledge and does not yet consume Team R’s official resource/port manifests.
- Prompt changes in `runner/aether2/prompts.py` should be treated as provisional. Keep them only for current behavior/tests, then do a final prompt pass after parent integration.

Exact next action for parent/orchestrator:
1. Read this handoff plus the direct thread handback.
2. Diff Team R’s runner/container/result-row manifests against the new Team H `env_contract` / blocker / `service_monitoring` payload shapes.
3. Integrate/normalize any cross-team schema naming deltas without weakening genericity.
4. Re-run parent-level integration checks.
5. Only then decide whether a final prompt pass is needed.

## Remaining process / container / VM / credential state

Local process/container state:
- No Codex subagents left running.
- No intentional persistent container/runtime launched by this thread remains tracked for ongoing work.
- Loop behavior tests launch temporary jobs/sessions inside temp workspaces only; no active test job is intentionally kept for handoff.

VM / Azure state:
- No Azure VM lifecycle action was taken from this thread.
- No evidence of an intentionally left-running VM/container for this handoff.

Credential / secret state:
- No credentials written into model-visible payloads.
- Receipt redaction remains active for sensitive fields.

