# Architect-As-Skill 15-Task Audit

Date: 2026-06-30

Scope:
- Architect-only runs only.
- No solver task attempts.
- No verifier model task attempts beyond architect-authored verifier prompt generation.
- No official grading or benchmark claim.

Implemented slice:
- Added first-class `verifier_system_prompt` to `HarnessConfigIR`.
- Added first-class config contract fields: `evidence_requirements`, `false_positive_risks`, `minimum_completion_evidence`.
- Compiled verifier prompt and evidence contract into `RuntimeConfigIR`, `CompiledRuntime`, `config_realization`, and verifier packets.
- Added task-specific architect verifier prompt to the model verifier system messages.
- Upgraded Workbench Architect system prompt into an architect-as-skill contract.
- Added exact visible smoke-test schema guidance.
- Added one repair retry for malformed/truncated architect JSON.
- Added deterministic architect quality rubric for solver prompt, verifier prompt, and config contract.
- Expanded `run_architect_only_eval.py` to 15 default tasks, Workbench-only default execution, concurrency, and prompt/config scoring.

Validation:
- `python3 -m compileall -q aether_next run_architect_only_eval.py` passed.
- `python3 -m pytest -q tests/test_vnext_workbench_ir.py tests/test_model_hooks.py` passed: 34 passed.
- `python3 -m pytest -q --ignore=tests/test_docker_runner.py` passed: 209 passed.

Run artifacts:
- Full real-task run:
  - `architect_only_eval_architect_skill_15_v5_32k_memory_clean/architect_only_eval.json`
  - `architect_only_eval_architect_skill_15_v5_32k_memory_clean/ARCHITECT_EVAL_REPORT.md`
- Stop-gate repair subset:
  - `architect_only_eval_architect_skill_subset_v6_stop_gate/architect_only_eval.json`
  - `architect_only_eval_architect_skill_subset_v6_stop_gate/ARCHITECT_EVAL_REPORT.md`
- Single provider no-output rerun:
  - `architect_only_eval_architect_skill_git_multibranch_v7/architect_only_eval.json`
  - `architect_only_eval_architect_skill_git_multibranch_v7/ARCHITECT_EVAL_REPORT.md`

Final score table uses the latest successful run per task:

| task | overall | solver | verifier | config | solver words | verifier words |
|---|---:|---:|---:|---:|---:|---:|
| filter-js-from-html | 10.0 | 10 | 10 | 10 | 492 | 335 |
| sparql-university | 10.0 | 10 | 10 | 10 | 709 | 506 |
| openssl-selfsigned-cert | 10.0 | 10 | 10 | 10 | 660 | 445 |
| video-processing | 10.0 | 10 | 10 | 10 | 670 | 427 |
| install-windows-3.11 | 9.67 | 9 | 10 | 10 | 695 | 571 |
| fix-git | 10.0 | 10 | 10 | 10 | 585 | 366 |
| gpt2-codegolf | 9.67 | 9 | 10 | 10 | 485 | 388 |
| extract-moves-from-video | 9.67 | 9 | 10 | 10 | 528 | 388 |
| git-multibranch | 10.0 | 10 | 10 | 10 | 697 | 498 |
| configure-git-webserver | 10.0 | 10 | 10 | 10 | 633 | 459 |
| qemu-alpine-ssh | 10.0 | 10 | 10 | 10 | 660 | 465 |
| financial-document-processor | 9.67 | 9 | 10 | 10 | 769 | 508 |
| vulnerable-secret | 10.0 | 10 | 10 | 10 | 585 | 402 |
| query-optimize | 10.0 | 10 | 10 | 10 | 450 | 469 |
| hf-model-inference | 10.0 | 10 | 10 | 10 | 635 | 400 |

Findings:
- The architect-as-skill upgrade materially improved prompt/config quality.
- Verifier prompts were consistently strong: all final selected outputs scored 10/10 for verifier prompt quality.
- Config contracts were consistently strong: all final selected outputs scored 10/10 for config contract quality.
- Parseability required a larger max-output cap for complex tasks; 32k plus repair retry was materially more reliable than 24k.
- Manual `query_memory` leakage was reduced by stronger architect instructions. The final selected 10/10 outputs satisfy the automatic-memory prompt rule.
- Remaining sub-10 solver scores are mostly rubric polish, not verifier/config failure. They should still be watched before solver reruns.

Next recommended slice:
- Add runtime automatic memory repeat interception so the solver no longer needs model-invoked memory discipline.
- Add a small runtime prompt lint before solver boot that can reject or repair prompts still mentioning manual `query_memory`.
- Then proceed to architect-only or verifier-only validation with the new fields in real verifier packets before returning to full solver task attempts.
