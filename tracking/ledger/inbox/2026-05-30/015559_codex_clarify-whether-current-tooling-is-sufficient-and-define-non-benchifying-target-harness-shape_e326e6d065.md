# Raw Ledger Update

- recorded_at_utc: 2026-05-30T01:55:59.143067+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: clarify whether current tooling is sufficient and define non-benchifying target harness shape
- event_type: decision
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: e326e6d065f215460fda7c6a1dbb362e439dff5176e4c6db3be6708496d16ad9
- commit_message: NONE - no tracked file changes
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-05-30/015559_codex_clarify-whether-current-tooling-is-sufficient-and-define-non-benchifying-target-harness-shape_e326e6d065.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: clarify whether current tooling is sufficient and define non-benchifying target harness shape
- event_type: decision
- summary: Concluded that the current baseline tool surface is not sufficient as a whole harness for acing TerminalBench-style evals, even though a terminal/bash primitive is the right base. The current raw_bash is a one-shot bash command runner rather than a persistent interactive tmux terminal, and lacks generic recovery, verification, context, service, and budget controllers.
- observations: blocks/tools/raw_bash.py exposes only a command string. runner/docker_sandbox.py executes each command through bash -lc or docker exec bash -lc, so shell-local state such as cd/export/interactive context does not persist across calls except through filesystem/background processes. Terminus-style agents use a mono-tool interactive terminal/tmux session, which keeps terminal state and supports interactive programs. Latest final-suite failures concentrate in service readiness, media/tool acquisition, exact schema/action grounding, TerminalBench artifact completion, and verifier-before-final behavior.
- inference: The best non-benchifying harness should preserve a generic terminal primitive but upgrade from thin stateless raw_bash to a terminal-session or typed-bash receipt layer plus task-family-agnostic controllers: environment preflight, filesystem/cwd contract, service readiness, verifier loop, bounded recovery, state capsule, and token/step budget control.
- evidence_paths: /Users/mohamud/Downloads/harnesseng/blocks/tools/raw_bash.py; /Users/mohamud/Downloads/harnesseng/runner/docker_sandbox.py; /Users/mohamud/Downloads/harnesseng/blocks/execution/flat_loop.py; /private/tmp/fhes_pull/full_runs_min/tracking/collab/final_harness_eval_suite/runs/20260529T234424Z; /private/tmp/fhes_pull/full_runs_min/tracking/collab/final_harness_eval_suite/runs/20260530T000729Z
- affected_components: tool surface; execution loop; recovery blocks; context blocks; verification blocks; service readiness mechanisms; TerminalBench adapter strategy
- decision_change: Do not solve failures by adding task-specific tools. Build a generic terminal-first harness with persistent session semantics and reusable receipt/checklist mechanisms.
- unresolved_questions: Whether to implement persistent tmux as a replacement for raw_bash or as an optional execution block; which exact subset of controllers gives best score/cost movement on mini-only rerun.
- confidence: high
- commit_message: NONE - no tracked file changes
```
