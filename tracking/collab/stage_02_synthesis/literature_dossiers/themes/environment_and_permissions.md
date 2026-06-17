LITERATURE_DOSSIER
- dossier_type: theme
- topic: environment_and_permissions
- scope:
  - Formal-source routing for Wave 05 claims about environment discovery, sandbox boundaries, approval/permission doctrine, cwd/workdir discipline, and authorization layers around tool execution.
  - Focus on official docs and papers that define containment and approval mechanisms without assuming those definitions prove behavioral enforcement.
- primary_sources:
  - `research/sources/docs/src_doc_5438a826fc4c/artifact.txt`
  - `research/sources/docs/src_doc_59532b247d8a/artifact.txt`
  - `research/sources/docs/src_doc_7b0e64d48534/artifact.txt`
  - `research/sources/docs/src_doc_c8a9703cc1eb/artifact.txt`
  - `research/sources/docs/src_doc_bfba858067cc/artifact.txt`
  - `research/sources/docs/src_doc_fc2c002988f2/artifact.txt`
  - `research/sources/docs/src_doc_bec8b9457702/artifact.txt`
  - `research/sources/papers/papers_text/src_pap_07a953e6fbbf.txt`
  - `research/sources/papers/papers_text/2603.05344.txt`
  - `research/sources/papers/papers_text/2602.07274.txt`
  - `research/sources/papers/papers_text/2603.00495.txt`
- secondary_sources:
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
- coverage_used:
  - `research/sources/docs/src_doc_5438a826fc4c/artifact.txt`
  - `research/sources/docs/src_doc_59532b247d8a/artifact.txt`
  - `research/sources/docs/src_doc_7b0e64d48534/artifact.txt`
  - `research/sources/docs/src_doc_c8a9703cc1eb/artifact.txt`
  - `research/sources/docs/src_doc_bfba858067cc/artifact.txt`
  - `research/sources/docs/src_doc_fc2c002988f2/artifact.txt`
  - `research/sources/docs/src_doc_bec8b9457702/artifact.txt`
  - `research/sources/papers/papers_text/src_pap_07a953e6fbbf.txt`
  - `research/sources/papers/papers_text/2603.05344.txt`
  - `research/sources/papers/papers_text/2602.07274.txt`
  - `research/sources/papers/papers_text/2603.00495.txt`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
- coverage_not_yet_used:
  - `research/sources/docs/src_doc_1ebb8bf0aacd/artifact.txt`
  - `research/sources/docs/src_doc_695f1b9755d4/artifact.txt`
  - `research/sources/docs/src_doc_78e1a708df4a/artifact.txt`
  - `research/sources/docs/src_doc_31348971d5a0/artifact.txt`
  - `research/sources/papers/papers_text/src_pap_d4370863a7e0.txt`
- evidence_classes_touched:
  - docs
  - papers
  - prior_wave_synthesis
  - coverage_register
- priority_sources_not_yet_read:
  - `research/sources/docs/src_doc_1ebb8bf0aacd/artifact.txt`
  - `research/sources/docs/src_doc_695f1b9755d4/artifact.txt`
  - `research/sources/docs/src_doc_78e1a708df4a/artifact.txt`
- formal_claims:
  - |
    Claim 1
    Observation: Codex and Claude docs both separate technical containment from prompting/approval behavior: sandbox mode controls what execution can do; permission/approval mode controls when the system asks before acting.
    Inference: Formal doctrine treats permissions as a two-layer mechanism (`capability boundary` plus `approval policy`) rather than a single switch.
    Confidence: high
    Evidence: `research/sources/docs/src_doc_5438a826fc4c/artifact.txt`, `research/sources/docs/src_doc_59532b247d8a/artifact.txt`, `research/sources/docs/src_doc_7b0e64d48534/artifact.txt`, `research/sources/docs/src_doc_c8a9703cc1eb/artifact.txt`
  - |
    Claim 2
    Observation: MCP roots spec requires explicit root exposure, path validation against roots, and path-traversal prevention; Claude docs define working-directory and additional-directory scope behavior.
    Inference: Formal environment-discovery guidance converges on explicit filesystem boundary declaration and path-scoped operations.
    Confidence: high
    Evidence: `research/sources/docs/src_doc_fc2c002988f2/artifact.txt`, `research/sources/docs/src_doc_7b0e64d48534/artifact.txt`
  - |
    Claim 3
    Observation: Permission-mode docs define distinct execution profiles (`default`, `plan`, `auto`, `dontAsk`, `bypassPermissions`) and explicitly characterize higher-autonomy modes as elevated risk or isolated-environment-only.
    Inference: Formal permission doctrine is risk-budgeted by mode, not merely by command allowlist.
    Confidence: high
    Evidence: `research/sources/docs/src_doc_c8a9703cc1eb/artifact.txt`, `research/sources/docs/src_doc_5438a826fc4c/artifact.txt`, `research/sources/docs/src_doc_7b0e64d48534/artifact.txt`
  - |
    Claim 4
    Observation: MCP tool and roots specs emphasize user confirmation/human-in-the-loop and consent as SHOULD-level guidance, while custom MCP guidance highlights prompt-injection and data exfiltration risk even with trusted servers.
    Inference: Formal ecosystem guidance acknowledges trust/safety pressure but does not claim universal hard enforcement by protocol alone.
    Confidence: medium
    Evidence: `research/sources/docs/src_doc_bfba858067cc/artifact.txt`, `research/sources/docs/src_doc_fc2c002988f2/artifact.txt`, `research/sources/docs/src_doc_bec8b9457702/artifact.txt`
    Weakener: Much of this is normative guidance text, not enforcement verification.
  - |
    Claim 5
    Observation: OAP formalizes a pre-action authorization layer and explicitly distinguishes it from sandboxing, arguing that sandboxing contains blast radius but does not itself enforce semantic authorization policy.
    Inference: Formal literature supports treating `authorization` as a separate mechanism family from `sandbox containment`.
    Confidence: high
    Evidence: `research/sources/papers/papers_text/src_pap_07a953e6fbbf.txt`
  - |
    Claim 6
    Observation: OPENDEV and TermiGen both foreground environment substrate integrity (self-contained dependencies, verified executable environments) as a prerequisite for stable long-horizon tool execution.
    Inference: Environment correctness is a first-order mechanism condition for tool reliability, not an incidental setup detail.
    Confidence: medium
    Evidence: `research/sources/papers/papers_text/2603.05344.txt`, `research/sources/papers/papers_text/2602.07274.txt`
    Weakener: These sources mainly establish environment engineering intent and training/evaluation setup, not broad cross-family production outcomes.
  - |
    Claim 7
    Observation: AI runtime infrastructure framing separates execution-time policy intervention from orchestration and post-hoc observability.
    Inference: Formal systems literature is moving toward runtime policy/control planes as explicit environment-permission substrates.
    Confidence: medium
    Evidence: `research/sources/papers/papers_text/2603.00495.txt`
    Weakener: Conceptual systems framing; limited direct coding-agent trajectory grounding in this source alone.
- benchmark_or_definition_notes:
  - `src_doc_fc2c002988f2` is the cleanest protocol definition for filesystem roots and boundary validation.
  - `src_pap_07a953e6fbbf` provides the strongest explicit definition split between pre-action authorization and sandbox containment.
  - `2602.07274` provides environment-validity definitions (build/solve verification loops) relevant to terminal substrate quality.
- mechanism_relevance:
  - Supports Wave 05 mechanism candidates for `filesystem-root boundary control`, `permission-mode risk budgeting`, and `authorization-vs-sandbox separation`.
  - Reinforces that environment and permission handling are distinct from generic planning or reasoning quality.
- failure_relevance:
  - Formal failures include: unauthorized tool calls, prompt-injection-driven exfiltration through connected tools, path-boundary violations, and environment non-executability.
  - Formal sources remain thinner on cross-task empirical rates for cwd/workdir corruption in production trajectories.
- eval_relevance:
  - Suggests eval surfaces should separately score containment, approval/authorization correctness, and environment reproducibility, rather than one merged safety metric.
- contradictions:
  - Formal docs describe mature permission and sandbox layers, but accepted Wave 03/04 carry-forward state still treats several operational safety claims as under-evidenced behaviorally and warns against over-reading formal rhetoric.
  - Formal permission/sandbox doctrine should not be promoted as proof of robust trajectory-level enforcement without trajectory/source reconciliation.
  - Evidence: `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`, `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`
- confidence_notes:
  - High confidence in formal boundary definitions (sandbox vs permissions, roots/path constraints, authorization vs containment) due direct protocol and docs alignment.
  - Medium confidence in practical enforcement strength because most sources are normative docs or architecture papers rather than direct trajectory reconciliation.
- open_questions:
  - Which formal sources best quantify false-negative and false-positive rates for approval classifiers across long-horizon coding workloads?
  - What formal evidence best connects cwd/workdir policy to measured success/failure in terminal trajectories?
- downstream_use:
  - Use this theme dossier to ground Wave 05 mechanism-map claims about environment discovery and permission boundaries without collapsing them into generic tool-use language.
- wave_01_literature_pressure_update_2026_04_10:
  - context: `failure_taxonomy` Wave 01 (`execution_control_and_terminal_failures`) formal-lane carry-forward.
  - observation: Formal policy/runtime sources consistently separate containment boundaries (sandbox/roots) from pre-action authorization and approval decisions.
  - inference: Wave 01 taxonomy should split environment/permission failures into at least `containment-boundary failure` vs `authorization-policy failure` to avoid false single-cause attribution.
  - confidence: high
  - evidence_paths:
    - `research/sources/docs/src_doc_5438a826fc4c/artifact.txt`
    - `research/sources/docs/src_doc_59532b247d8a/artifact.txt`
    - `research/sources/docs/src_doc_7b0e64d48534/artifact.txt`
    - `research/sources/docs/src_doc_c8a9703cc1eb/artifact.txt`
    - `research/sources/docs/src_doc_fc2c002988f2/artifact.txt`
    - `research/sources/papers/papers_text/src_pap_07a953e6fbbf.txt`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/literature_papers_docs_analyst.md`
- wave_01_execution_control_and_terminal_failures_update:
  - observations:
    - execution-control failures in Wave 01 frequently cross environment boundaries (terminal process teardown, browser crash recovery, stale resume index, permission-hook bypass).
    - source-backed surfaces in DeepAgents and KIRA show different environment-governance philosophies (direct local shell vs managed process/session tooling).
  - inferences:
    - environment/permission policy should be modeled as a control-plane reliability requirement, not only as security posture.
    - permission-routing mismatch is a direct contributor to execution drift and unsafe fallback behavior.
  - confidence:
    - high for issue-level failure existence
    - medium for uniform prevalence across all harness families
  - evidence_paths:
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/local_shell.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_manager.py`
    - `research/sources/issues/src_iss_72d11ef0f608/artifact.txt`
    - `research/sources/issues/src_iss_da41417f5655/artifact.txt`
    - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
    - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/execution_control_and_terminal_failures.md`
- wave_04_failure_taxonomy_formal_pressure_update_2026_04_11:
  - context: `failure_taxonomy` Wave 04 (`tools_environment_coordination_and_long_horizon_failures`) formal-lane update.
  - observations:
    - formal docs and OAP paper consistently separate capability containment (sandbox/roots/runtime limits) from pre-action authorization/approval policy.
    - MCP roots/tools specs explicitly frame root-boundary/path validation and human consent as first-class control surfaces.
    - terminal-agent papers tie environment executability and environment verification loops to downstream reliability under long-horizon execution.
  - inferences:
    - Wave 04 failure cards should preserve separate attribution for `permission-policy/runtime mismatch` and `containment/roots-path boundary mismatch`.
    - `cwd/workdir/path contract failure` should remain distinct from generic coordination or planning failures.
    - environment integrity should be treated as a failure-bearing substrate, not only setup hygiene.
  - confidence:
    - high for boundary-definition claims
    - medium for cross-system prevalence claims
  - evidence_paths:
    - `research/sources/docs/src_doc_5438a826fc4c/artifact.txt`
    - `research/sources/docs/src_doc_59532b247d8a/artifact.txt`
    - `research/sources/docs/src_doc_7b0e64d48534/artifact.txt`
    - `research/sources/docs/src_doc_c8a9703cc1eb/artifact.txt`
    - `research/sources/docs/src_doc_fc2c002988f2/artifact.txt`
    - `research/sources/docs/src_doc_bfba858067cc/artifact.txt`
    - `research/sources/papers/papers_text/src_pap_07a953e6fbbf.txt`
    - `research/sources/papers/papers_text/2602.07274.txt`
    - `research/sources/papers/papers_text/2603.05344.txt`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/literature_papers_docs_analyst.md`
- wave_04_trajectory_lane_reconciliation_2026_04_11:
  - trajectory_alignment:
    - required extract/cancellation slices show practical permission-runtime friction (`externally-managed-environment`, root install warnings, busy system paths) coupled with tool and long-horizon pressure.
  - inference:
    - keep permission-policy vs runtime-capability separation explicit in Wave 04 failure cards; do not fold into generic setup noise.
  - evidence_paths:
    - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
    - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
  - confidence: medium
- wave_04_codebase_source_reconstruction_reconciliation_2026_04_11:
  - source_reconciliation_inputs:
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/codebase_source_reconstruction_analyst.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/codebase_support_tool_environment_failure_map.md`
  - observations:
    - source-backed families explicitly separate policy gating from runtime capability (deepagents CLI vs backend, KiraClaw allow/deny/ask vs KIRA-Slack bypassPermissions).
    - filesystem-root and cwd semantics are heterogeneous across families and match the formal requirement to treat boundary control as a first-class contract.
  - inference:
    - formal environment/permission doctrine remains aligned with Wave 04 source evidence; keep `permission-policy/runtime mismatch` and `cwd/path contract failure` as distinct failure families.
  - confidence:
    - high
  - evidence_paths:
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/local_shell.py`
    - `research/sources/codebases/deepagents/libs/cli/deepagents_cli/config.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/settings.py`
    - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/operator/agent.py`
    - `research/sources/codebases/a-evolve/agent_evolve/agents/swe/env.py`
