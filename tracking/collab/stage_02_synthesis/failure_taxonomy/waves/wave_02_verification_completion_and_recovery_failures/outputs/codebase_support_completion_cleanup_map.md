# Codebase Support Completion Cleanup Map

## Scope
- Wave: `failure_taxonomy/wave_02_verification_completion_and_recovery_failures`
- Lane: `codebase/source-reconstruction`
- Purpose: map completion signals, acceptance gates, and cleanup obligations across source families.

## Completion/Cleanup Layers
| System | Completion Signal | Acceptance Gate | Cleanup/Hygiene Gate | Failure Risk if Misread | Evidence Paths |
|---|---|---|---|---|---|
| `deepagents` | End-of-run agent answer and produced artifacts. | `TrajectoryScorer.success(...)` hard checks when configured; benchmark-specific replay/state checks in tau2; optional judge grading. | Not universally mandatory in source; often task-authored in-run checks in trajectories. | Treating `.expect(...)` diagnostics or weak text-substring checks as equivalent to hard verifier proof can create false completion. | `research/sources/codebases/deepagents/libs/evals/tests/evals/utils.py`, `research/sources/codebases/deepagents/libs/evals/tests/evals/external_benchmarks.py`, `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/evaluation.py`, `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt` |
| `KIRA` | `task_complete` tool call intent. | Two-step completion confirmation prompt with checklist, then second confirmation call. | Prompt explicitly requires minimal-state-change review before completion. | Checklist protocol can still be over-claimed if tests are weak or contradictions remain unresolved in-run. | `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`, `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt`, `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt` |
| `a-evolve` | `submit("DONE")` tool sets submitted state and stops loop. | External benchmark adapter computes pass/fail using trajectory outputs and verifier artifacts. | Cleanup is not an intrinsic submit gate; depends on benchmark checks and test scripts. | Confusing `submit` with success can cause false completion; fallback output parsing (`passed=True` prefix) is fragile if trajectory metadata drifts. | `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/react_solver.py`, `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/tools.py`, `research/sources/codebases/a-evolve/agent_evolve/benchmarks/tb2/terminal2.py` |
| `BigAI` (behavioral only) | Planner/executor report task-ready state. | Separate verifier role emits `verification_result_status` and `finish_verification` events. | Delivery directory cleanliness appears as explicit verifier acceptance criterion in sampled runs. | Verifier `PASSED` does not always imply final run success; internal acceptance policy remains hidden. | `research/analysis/bigai_trace_layer/output/question_answers.json`, `research/analysis/bigai_trace_layer/output/answered_questions.md`, `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt` |
| `local harness (blocks/runner/evals)` | Intended by interface only; no concrete implementation in read files. | `runner/evaluator.py` and `evals/verification_eval.py` are currently specification-level stubs. | `blocks/verification/*` and `blocks/recovery/*` include named variants but no execution logic yet. | Immediate risk is taxonomy collapse in local code because completion/verification/cleanup layers are not implemented yet. | `runner/evaluator.py`, `evals/verification_eval.py`, `blocks/verification/trust_model.py`, `blocks/verification/double_confirm.py`, `blocks/recovery/rollback.py` |

## Failure Taxonomy Implications
- Preserve separate cards for:
  - completion signal asserted
  - verifier/adjudicator pass
  - cleanup/delivery hygiene pass
  - final benchmark acceptance
- Attribute mixed failures to the specific failed layer first, then to model/harness/environment/benchmark-contract causes.
- Keep BigAI as behavioral reconstruction and avoid source-backed wording.
