# Aether-Next Goal Evidence - 2026-07-04

## Goal

Move the canonical Aether-Next harness toward the target architecture:

- architect owns workbench design and role prompts
- solver owns solving and only calls verifier by submit
- verifier is a read-only current-state inspector
- harness owns substrate, routing, safety, receipts, traces, and runtime invariants only
- official grader stays external
- no deterministic task-specific completion authority
- no silent fallback or fake configurability

## Implementation Slices Completed

1. Strengthened `HarnessConfigIR` parsing so architect configs must include non-empty task understanding, success definition, evidence requirements, minimum completion evidence, verifier success criteria, verifier required evidence, and canonical `model_verifier_policy.runs_on == ["solver_submit"]`.
2. Added durable in-progress result rows in `run_pilot.py` before each task attempt starts.
3. Removed proof-contract authority from completion and finding resolution. Proof-contract remains evidence only.
4. Normalized historical replay config metadata while keeping live architect config parsing strict.
5. Upgraded the architect prompt so solver prompts must include failed-check/verifier-feedback recovery and verifier prompts must explicitly say read-only/current-state/inspect.
6. Changed uninspected verifier completion from an opaque protocol error into a visible non-completion path, then improved it further by forcing a minimal generic read-only inspection before accepting `completed`.
7. Added canonical submit throttling: if active verifier findings exist and the solver has not produced intervening action/evidence, repeated submit skips the verifier instead of spending another verifier call.
8. Added a verifier prompt/runtime rule and architect-quality rubric item requiring solver-authored validation commands, recomputation scripts, local checks, and self-reports to be treated as evidence to audit rather than proof.
9. Updated the reset/canonical plans with verifier packet evidence-hygiene requirements: no `solver_claim`, `submit_summary`, or privileged solver-proof fields; solver commands/checks labeled as audit trail; proof-contract removed or quarantined from verifier judgment; verifier inspection prioritizes raw state.
10. Removed `proof_contract_analysis` from active verifier packets and replaced neutral top-level `latest_command_results` with `solver_authored_evidence.command_results` marked `authority: audit_trail_only`.
11. Added verifier packet regression coverage proving forbidden solver/proof fields are absent and solver command history remains visible only as audit trail.
12. Quarantined `proof_contract` from the active certified runtime path by removing kernel proof-contract receipts and context packet `proof_contract_status`; the legacy module remains only as reference/tested analyzer code until the physical deletion/archive slice.
13. Removed `compiler.guaranteed_default_ir()` from certified workbench architect/config failure handling. Failed workbench initialization now carries an explicit non-executable invalid-workbench IR with `compiled=None` and `config_invalid_blockers`, rather than a generic safe-default placeholder.
14. Removed `ModelHooks` architect/reconfigure safe-default IR fabrication. Architect or reconfigure parse/model failure now raises `ModelOutputError`; the baseline resolver converts architect parse failure into visible `config_invalid` instead of returning a generic runtime config.
15. Removed the remaining baseline/contract `compiler.guaranteed_default_ir()` fallback branches, deleted the now-unused `ConfigCompiler.guaranteed_default_ir()` method, and removed the dead kernel `config_fallback` receipt emitter. Unrepaired fatal config now fails closed as `config_invalid`; genuine generic repair still produces `config_repair`.
16. Tightened reference architect mode evidence: Docker runner now uses the shared adapter mode-selection helper instead of duplicating it, `run_pilot.py` correctly passes `--allow-reference-architect-mode` through to the Docker runner, and every pilot/adapter/Docker row records `architect_mode` plus `reference_architect_mode`.
17. Improved verifier forced-inspection selection so an uninspected `completed` verdict triggers read-only inspection of both the final artifact and a recently read raw/source file before receipt/history context. Added a verifier-only regression where raw source contradicts solver-authored recomputation and the verifier returns `needs_repair`.
18. Surfaced bounded `raw_state_candidates` from EnvMap into verifier packets via compile-time realization metadata. Candidates are labeled `authority: candidate_only` and come from generic file-map hints such as likely inputs and instruction-referenced visible paths, excluding declared outputs and likely tests/checkers. Forced verifier inspection now uses these candidates when no solver file-read evidence exists.
19. Extended the verifier-only eval board with `solver_claim_conflicts_with_raw_state`: a solver-authored command claims `summary.csv` matches `data/events.log`, while the packet exposes `data/events.log` only as non-authoritative raw-state candidate evidence. The expected verdict is `uncertain_missing_evidence`, not completion; the offline validator now checks the raw-state candidate and `solver_authored_evidence.authority == audit_trail_only`.
20. Removed the stale `compiler.guaranteed_default_ir()` call from `replay_resume.py`. Replay/debug config reconstruction now fails closed with explicit `config_invalid_blockers` when a trace config cannot be compiled, and the legacy/reference inventory was updated to stop claiming safe-default config fabrication still exists.
21. Ran a fresh 15-task architect-only 5.4-mini component board after packet-hygiene changes. All 15 workbench configs scored 10/10 overall, with solver prompt 10/10, verifier prompt 10/10, config contract 10/10, no workbench errors, no warnings, no rejected config items, and `model_verifier_policy.runs_on == ["solver_submit"]`.
22. Ran a fresh 5.4-mini verifier-only model board on the six packet-hygiene cases. All six parsed, were actionable, and passed offline validation. The new `solver_claim_conflicts_with_raw_state` case returned `uncertain_missing_evidence`, not `completed`, and asked to inspect `data/events.log` / `summary.csv` rather than trusting the solver-authored command.

## Targeted Gates

All commands below were run from `/Users/mohamud/Downloads/harnesseng/aether_next_build`.

- `python3 -m pytest -q tests` -> `283 passed`
- `python3 run_verifier_only_eval.py --mode fake --out-dir verifier_only_eval_20260704_goal_postfix_after_forced_inspection` -> 5/5 parseable, evidence-bound, actionable
- `python3 run_verifier_prompt_replay_eval.py --out-dir verifier_prompt_replay_eval_20260704_goal_postfix_after_forced_inspection` -> architect prompt improved actionability
- `python3 run_trace_verifier_replay_ab.py --mode fake --out-dir trace_verifier_replay_ab_20260704_goal_postfix_after_uninspected_fix` -> 3/3 architect prompt improved
- `python3 run_envmap_audit.py --out-dir envmap_audit_20260704_goal_postfix` -> 90 indexed tasks
- EnvMap spot check: `ENVMAP_SPOTCHECK_20260704.md`
- Post false-clean targeted architect eval: `architect_only_eval_20260704_goal_postfix_solver_validation_audit/` -> 10/10, with verifier prompt explicitly auditing solver-authored validation rather than trusting it.
- Packet hygiene focused gate: `python3 -m pytest -q tests/test_vnext_memory_context_verifier.py tests/test_runtime_enforcement.py tests/test_model_hooks.py` -> `71 passed`
- Full Aether-Next gate after packet cleanup: `python3 -m pytest -q tests` -> `284 passed`
- Proof-contract active-path quarantine focused gate: `python3 -m pytest -q tests/test_runtime_enforcement.py tests/test_vnext_memory_context_verifier.py tests/test_kernel.py tests/test_completion.py` -> `72 passed`
- Full Aether-Next gate after active proof-contract quarantine: `python3 -m pytest -q tests` -> `284 passed`
- Workbench fallback cleanup focused gate: `python3 -m pytest -q tests/test_kernel_config.py tests/test_vnext_configurability.py tests/test_kernel.py tests/test_features.py tests/test_model_hooks.py` -> `79 passed`
- Full Aether-Next gate after workbench fallback cleanup: `python3 -m pytest -q tests` -> `284 passed`
- ModelHooks safe-default removal focused gate: `python3 -m pytest -q tests/test_model_hooks.py tests/test_kernel_config.py tests/test_vnext_configurability.py tests/test_kernel.py` -> `63 passed`
- Full Aether-Next gate after ModelHooks safe-default removal: `python3 -m pytest -q tests` -> `285 passed`
- Baseline/contract safe-default removal focused gate: `python3 -m pytest -q tests/test_kernel_config.py tests/test_features.py tests/test_kernel.py tests/test_repair.py tests/test_model_hooks.py` -> `58 passed`
- Full Aether-Next gate after baseline/contract safe-default removal: `python3 -m pytest -q tests` -> `285 passed`
- Reference-mode quarantine metadata focused gate: `python3 -m pytest -q tests/test_run_pilot.py tests/test_run_adapter.py tests/test_docker_runner.py tests/test_kernel_config.py` -> `22 passed`
- Full Aether-Next gate after reference-mode metadata cleanup: `python3 -m pytest -q tests` -> `285 passed`
- Verifier raw-state inspection focused gate: `python3 -m pytest -q tests/test_model_hooks.py tests/test_vnext_memory_context_verifier.py tests/test_runtime_enforcement.py` -> `73 passed`
- Full Aether-Next gate after verifier raw-state inspection improvement: `python3 -m pytest -q tests` -> `287 passed`
- EnvMap raw-state candidate surfacing focused gate: `python3 -m pytest -q tests/test_model_hooks.py tests/test_vnext_memory_context_verifier.py tests/test_vnext_configurability.py` -> `86 passed`
- Full Aether-Next gate after EnvMap raw-state candidate surfacing: `python3 -m pytest -q tests` -> `289 passed`
- Packet-hygiene verifier-only board: `python3 run_verifier_only_eval.py --mode fake --out-dir verifier_only_eval_20260704_goal_packet_hygiene_v2` -> 6/6 parseable, evidence-bound, actionable
- Packet-hygiene verifier-only validation: `python3 validate_verifier_only_eval.py verifier_only_eval_20260704_goal_packet_hygiene_v2 --report VERIFIER_ONLY_PACKET_HYGIENE_VALIDATION.md` -> `ok: true`
- Packet-hygiene focused gate: `python3 -m pytest -q tests/test_chatgpt_integration_scenarios.py tests/test_chatgpt_broad_slice.py tests/test_model_hooks.py tests/test_vnext_memory_context_verifier.py` -> `74 passed`
- Full Aether-Next gate after packet-hygiene verifier-only board: `python3 -m pytest -q tests` -> `289 passed`
- Replay safe-default cleanup grep: `rg -n "guaranteed_default_ir|guaranteed safe default|_safe_default_ir|_safe_default_ir_from_compiled" aether_next_build/aether_next aether_next_build/*.py aether_next_build/tests aether_next_build/LEGACY_REFERENCE_SURFACE_INVENTORY_20260704.md` -> no code hits; one historical inventory note
- Replay safe-default cleanup focused gate: `python3 -m pytest -q tests/test_kernel_config.py tests/test_model_hooks.py tests/test_features.py tests/test_chatgpt_broad_slice.py` -> `52 passed`
- Full Aether-Next gate after replay cleanup: first run had a transient Docker `inspect` timeout in `tests/test_docker_runner.py::TestDockerExecExecutor::test_teardown_removes_container`; isolated rerun passed (`1 passed`), `docker ps` showed no leftover containers, and clean full rerun `python3 -m pytest -q tests` -> `289 passed`
- Architect-only component board: `python3 run_architect_only_eval.py --out-dir architect_only_eval_20260704_packet_hygiene_15 --concurrency 3 --effort high` -> 15 records; min/avg workbench score 10.0/10; no errors/warnings/rejected config items; every row `runs_on=["solver_submit"]`
- Verifier-only 5.4-mini component board: `python3 run_verifier_only_eval.py --mode model --out-dir verifier_only_eval_20260704_packet_hygiene_54mini_v2` -> 6/6 parseable, evidence-bound, actionable
- Verifier-only 5.4-mini validation: `python3 validate_verifier_only_eval.py verifier_only_eval_20260704_packet_hygiene_54mini_v2 --report VERIFIER_ONLY_PACKET_HYGIENE_54MINI_V2_VALIDATION.md` -> `ok: true`
- Verifier-only model-board focused gate: `python3 -m pytest -q tests/test_chatgpt_integration_scenarios.py tests/test_chatgpt_broad_slice.py tests/test_model_hooks.py tests/test_vnext_memory_context_verifier.py` -> `74 passed`
- Full suite after verifier-only model-board patch: `python3 -m pytest -q tests` -> `288 passed, 1 error`; error was Docker Desktop returning `500 Internal Server Error` during `docker run` setup in `tests/test_docker_runner.py::TestDockerExecExecutor::test_write_and_read_file`
- Docker flake isolation: `docker version --format '{{.Server.Version}}'` -> `29.0.1`; isolated rerun `python3 -m pytest -q tests/test_docker_runner.py::TestDockerExecExecutor::test_write_and_read_file` -> `1 passed`
- Non-Docker suite after verifier-only model-board patch: `python3 -m pytest -q tests -k 'not DockerExecExecutor and not docker'` -> `279 passed, 10 deselected`

## Architect-Only Evidence

Pre-fix 10-task architect eval:

- Path: `architect_only_eval_20260704_goal_postfix_10/`
- Average: 9.7/10
- Missing criteria in 7/10 rows, mainly failed-check/verifier-feedback handling and read-only/state wording.

Post-fix 10-task architect eval:

- Path: `architect_only_eval_20260704_goal_postfix_10_v2/`
- Result: 10/10 rows scored 10/10 for solver prompt, verifier prompt, and config contract.
- No bad contracts.
- All configs kept `model_verifier_policy.runs_on == ["solver_submit"]`.

## Live Attempt Evidence

### Invalid launch: `raman-fitting`

- Path: `local_goal_runs/20260704T202419Z_goal_local_raman/`
- Status: invalid/interrupted before container start.
- Finding: local Docker did not have `alexgshaw/raman-fitting:20251031`; launch stayed image-acquisition-bound and produced no agent-loop evidence.

### Diagnostic live run: `filter-js-from-html`

- Path: `local_goal_runs/20260704T202927Z_goal_local_filter/`
- Solver reached submit at step 23.
- Verifier prompt was architect-owned and correctly framed as read-only current-state inspection.
- Finding: uninspected completed was rejected, but the loop became opaque and timeout handling did not produce a terminal row before manual interrupt.
- Follow-up fix: visible non-completion feedback plus submit throttling.

### Throttle live run: `log-summary-date-ranges`

- Path: `local_goal_runs/20260704T212830Z_goal_local_logsummary_throttle/`
- Official grader reward: 1.0.
- Kernel status: incomplete.
- Verifier calls: 2 (`step_0002`, `step_0006`), not repeated on every submit.
- Finding: submit throttle worked, but verifier still failed to inspect deeply enough and remained uncertain.
- Follow-up fix: forced generic read-only inspection before accepting completed.

### Forced-inspection live run: `log-summary-date-ranges`

- Path: `local_goal_runs/20260704T213739Z_goal_local_logsummary_forcedinspect/`
- Kernel status: completed.
- Verifier final verdict: completed.
- Verifier calls: 1.
- Verifier inspection receipt present.
- Official grader reward: 0.0.
- Grader failure: expected `today,ERROR,370`, got `today,ERROR,414`.
- Classification: verifier false-clean, not trigger spam. The verifier accepted the solver's flawed recomputation evidence instead of independently checking the log-line semantics deeply enough.
- Follow-up repair: the verifier runtime contract, forced-inspection follow-up message, architect prompt, and architect-quality rubric now explicitly require solver-authored validation/recomputation to be audited rather than treated as proof. A targeted architect-only rerun on this task scored 10/10 with that wording present.

### Packet-hygiene final single attempt: `log-summary-date-ranges`

- Path: `local_goal_runs/20260704T_packet_hygiene_logsummary/`
- Backend: local Docker-backed `run_pilot.py` because this shell has Azure CLI but no authenticated/configured VM control-plane state (`az account show` produced no account JSON; no VM resource env vars were present).
- Command: `python3 run_pilot.py --tasks log-summary-date-ranges --out local_goal_runs/20260704T_packet_hygiene_logsummary/results.json --trace-dir local_goal_runs/20260704T_packet_hygiene_logsummary/traces --snapshot-dir local_goal_runs/20260704T_packet_hygiene_logsummary/snapshots --max-steps 80 --run-timeout-s 3600 --effort high`
- Architect mode: `workbench`; `reference_architect_mode=false`.
- Architect fallback/repair codes: none (`architect_fallback_codes=[]`, `architect_repair_codes=[]`).
- Solver steps: 5 terminal step / 6 trace steps.
- Reconfigurations: 0.
- Verifier calls: 1, on solver submit.
- Verifier inspection: executed before completion (`read_file`, `read_file`, `inspect_recent_receipts`).
- Kernel status: `completed`.
- Verifier final verdict: `completed`.
- Official grader reward: `1.0`; visible grader tests passed `2/2`.
- Final `summary.csv` includes the previously failed row correctly: `today,ERROR,370`.
- External state: no task Docker container remained after completion (`docker ps` returned no rows).

Interpretation:

- This is the first fresh post-packet-hygiene task row where verifier, kernel, and official grader agree on completion.
- The run directly targets the prior false-clean family and shows the solver produced the correct raw-log-derived CSV in 5 steps rather than looping.
- Caveat: the trace records verifier inspection kind summaries but not separate verifier packet/result bundles because `AETHER_VERIFIER_EVIDENCE_DIR` was not set for this local run. Future certified/VM runs should set that env var so packet, inspection result, and parsed verdict are persisted separately.

## Current Truth

What is substantially fixed:

- Architect config is strict and non-hollow.
- Architect prompt quality now tests cleanly across a 10-task diverse sample.
- Solver-submit-only verifier triggering is enforced.
- Repeated submit no longer causes repeated verifier calls without intervening evidence.
- Verifier now performs read-only inspection before `completed` can be accepted.
- Architect/verifier prompts now explicitly distinguish solver-authored checks from independent verifier evidence.
- Deterministic proof-contract no longer owns completion, finding resolution, or active verifier packet context.
- Deterministic proof-contract no longer emits active kernel receipts or solver context status in the certified path.
- Solver command/check history remains visible to the verifier, but under `solver_authored_evidence` as audit trail rather than neutral proof.
- Certified workbench architect/config failure no longer uses the compiler's guaranteed safe default as its failure artifact.
- `ModelHooks.architect()` and `ModelHooks.reconfigure()` no longer fabricate safe-default `RuntimeConfigIR` objects on bad model output.
- No active resolver calls `compiler.guaranteed_default_ir()`; the method has been deleted.
- No replay/debug script calls `compiler.guaranteed_default_ir()`; stale replay resume behavior now fails closed with explicit blockers.
- Reference architect modes remain explicitly opt-in only and are now visible in result rows via `reference_architect_mode=true`.
- Forced verifier inspection now prioritizes raw state: final artifact plus recently read raw/source file before generic receipt/history context.
- Verifier packets now include non-authoritative `raw_state_candidates` from EnvMap so the verifier can inspect raw inputs even when the solver has not read them yet.
- The verifier-only board now contains a solver-authored-claim contamination sentinel and the validator enforces raw-state candidate visibility plus audit-only solver evidence labeling.
- A fresh 15-task architect-only model board shows the architect still creates strong task-specific solver/verifier prompts and valid configs after the reset changes.
- A fresh verifier-only 5.4-mini model board shows the verifier does not complete when solver-authored evidence claims success but raw source state has not been independently inspected.
- In-progress rows make launch/invalidation visible.

What is not fixed:

- Live trace/progress is still not streamed mid-run; monitoring is opaque until terminal trace write or verifier bundles appear.
- Verifier inspection depth remains insufficient until revalidated end-to-end. Generic forced inspection supplies file/receipt/history evidence, and prompts now warn against over-trusting solver-authored recomputation receipts, but this has only been validated by architect-only and unit/diagnostic gates, not by a fresh passing live grader row.
- Result rows can show `kernel_status=completed` and `official_grader_status=fail`; this is now honestly captured as verifier/grader disagreement, but the verifier needs better evidence selection before promotion.
- Reconfigure can be triggered by solver parse failures in live runs; it remained honest, but step efficiency still needs improvement.

## Recommended Next Slice

Target verifier evidence selection and agreement, not completion plumbing.

Next, strengthen verifier evidence selection beyond the first verifier-only diagnostic for "solver-authored recomputation is wrong":

- fixture family: generated artifact plus raw source files
- solver receipt: plausible but flawed recomputation
- verifier packet: artifact, receipts, source files, and false-positive traps
- expected verifier verdict: `needs_repair` or `uncertain_missing_evidence`, never `completed`
- known-bad: verifier accepts the solver's recomputation without independently checking source semantics
- ceiling: verifier reads raw evidence or requests/reruns an independent check and catches the mismatch

Candidate generic mechanism:

- let architect express verifier evidence priorities as read-only inspection targets
- compile them into verifier inspection hints, not completion authority
- when success depends on source-derived calculations, force/source-prioritize inspection of raw inputs or a verifier-owned rerun check before `completed`

Keep/kill criterion:

- keep only if verifier/grader false-clean rate drops on the diagnostic family and `log-summary-date-ranges` no longer completes with reward 0
- kill if it only makes verifier more pessimistic without catching semantic mismatches
