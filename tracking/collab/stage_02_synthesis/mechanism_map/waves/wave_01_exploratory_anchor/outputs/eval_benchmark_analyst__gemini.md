EVAL_BENCHMARK_OUTPUT
- artifact: mechanism_map
- role: eval/benchmark analyst
- preflight_scope_confirmed: Yes. Anchored to `corpus__captured_for_synthetic_prep.json` and the organizer matrices.
- preflight_planned_read_order:
  1. Local harness eval files (`evals/`)
  2. `deepagents` lib evals and Harbor README
  3. `ImpossibleBench` benchmark capture
  4. `SWE-bench Verified` benchmark capture
- preflight_critical_sources_selected:
  - `evals/verification_eval.py`, `evals/context_eval.py`, `evals/step_efficiency_eval.py`
  - `research/sources/codebases/deepagents/libs/evals/README.md`
  - `research/sources/benchmarks/src_bnm_8c3b5dc456f5/capture.json` and `artifact.txt`
  - `research/sources/benchmarks/src_bnm_e5f985948a0e/capture.json` and `artifact.txt`
- preflight_coverage_risks: The source repos for `ImpossibleBench` and `SWE-bench Verified` are captured as text/html artifacts, so direct grader code analysis is limited to the descriptions available. Harbor grader logic is blackboxed behind the `harbor run` command, though we know it provides binary/continuous rewards based on test pass rates.
- preflight_likely_blind_spots: Detailed insight into how ImpossibleBench constructs the "impossible" splits is limited without the actual test datasets. DeepAgents Harbor implementation details (e.g., how the sandboxes specifically score tasks) are abstracted behind the benchmark definitions.
- preflight_blockers: None.
- coverage_used:
  - `evals/context_eval.py`
  - `evals/step_efficiency_eval.py`
  - `evals/verification_eval.py`
  - `research/sources/codebases/deepagents/libs/evals/README.md`
  - `research/sources/benchmarks/src_bnm_8c3b5dc456f5/artifact.txt`
  - `research/sources/benchmarks/src_bnm_e5f985948a0e/artifact.txt`
- coverage_not_yet_used:
  - Actual codebase files for ImpossibleBench/SWE-bench (not fully mirrored, just captures).
  - Trajectory logs of eval runs (which would be under `research/sources/trajectories/`).
- evidence_classes_touched: relevant local harness code, benchmark captures, mirrored codebases.
- priority_sources_not_yet_read: Full trajectory logs corresponding to Terminal Bench 2.0 evaluation runs.

- benchmark_contracts:
  - **Terminal Bench 2.0 (Harbor)**: Contract expects the agent to resolve tasks entirely via terminal interactions, evaluating capabilities like terminal execution, Git multi-branch handling, and environment setup.
  - **ImpossibleBench**: Contract expects an agent to either solve a valid task or fail on an "impossible" task. If it passes an "impossible" task, it is penalized for "cheating" or specification gaming.
  - **SWE-bench Verified**: Contract expects the agent to resolve Github issues via patches, evaluated strictly by bash-only ReAct loops (mini-SWE-agent) to baseline LMs, or full tool scaffolds for multi-file agents.
  - **Local Evals**: Contract focuses on meta-mechanisms: context management (avoiding overflow), step efficiency (overhead vs. effectiveness), and verification accuracy (catching false positives/negatives).

- grader_and_verifier_patterns:
  - **Harbor**: Uses an automated sandbox (Docker/Daytona/Modal) to execute tasks and scores them via `harbor_reward` (0.0 to 1.0) based on test pass rates.
  - **ImpossibleBench**: Employs an LLM Judge (`claude-opus-4`) for binary classification of "cheating vs legit" based on transcript dumps.
  - **Local Evals**: Tests are categorized by capability (`memory`, `hitl`, `tool_usage`) and annotated via `pytest.mark.eval_category`. Tests explicitly target whether verification blocks catch false positives.

- replay_or_reproducibility_notes:
  - **DeepAgents**: Reproducibility is maintained via LangSmith trajectories (ATIF format) and Harbor's isolated sandboxes (Docker/Daytona). Runs can be tracked via `LANGSMITH_EXPERIMENT`.
  - **SWE-bench Verified**: Relies heavily on version-pinning the `mini-SWE-agent` to ensure reproducible baselines, acknowledging that tool-calling (2.x) vs parsing (1.x) changes the nature of the evaluation.

- gaming_or_proxy_risks:
  - **ImpossibleBench**: Directly studies gaming risks. Tests reveal that standard pass/fail metrics may mask agents taking specification-violating shortcuts.
  - **Harbor / Terminal Bench 2.0**: Proxy risks exist if tasks like `sqlite-with-gcov` are solved by hallucinating paths or bypassing the intended build process if the grader only checks the final output file rather than the trajectory. Evals note patterns like "Hallucinated Paths" and "Poor Planning", where agents guess rather than verify via `ls`.

- upstream_artifact_implications:
  - **Mechanism Map**: The `evals` evidence points to mechanisms like "Context Management" (sliding window, structured sections) and "Verification Accuracy" as critical. The `ImpossibleBench` evidence demands a mechanism for "Specification Adherence" or "Cheating Prevention", showing that simple pass/fail mechanisms are insufficient.
  - The map must include "Terminal Sandbox Execution" (Harbor) as a core execution mechanism.

- contradiction_notes:
  - There is a tension between SWE-bench's "Bash Only" baseline (no tools, just bash ReAct) and DeepAgent's "Full Scaffold" (with specific `write_todos`, `task` tools). Benchmarking an LM vs an Agent architecture often conflates model capability with harness mechanism strength.
  - ImpossibleBench shows that high reward scores might indicate gaming rather than capability, directly contradicting naive reward-maximization approaches.

- confidence_notes:
  - High confidence in the structure of the DeepAgents eval harness and the goals of SWE-bench/ImpossibleBench.
  - Medium confidence in the exact grading logic of Harbor and ImpossibleBench, as the underlying test datasets and specific grader code were not fully available in the text captures.

- open_questions:
  - How do the "impossible" splits in ImpossibleBench actually manifest in the trajectories?
  - Does the local `verification_eval.py` use a static grader or an LLM-as-a-judge like ImpossibleBench?

- next_hand_off_target: contradiction_analyst
