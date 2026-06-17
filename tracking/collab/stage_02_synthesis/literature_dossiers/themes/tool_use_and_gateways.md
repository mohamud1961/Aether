LITERATURE_DOSSIER
- dossier_type: theme
- topic: tool_use_and_gateways
- scope:
  - Formal-source routing for Wave 05 claims about tool schemas, tool discovery/load strategy, runtime tool routing, and gateway control under large tool surfaces.
  - Focus on papers and official docs that specify how tools are exposed, selected, validated, and rerouted when tool environments are noisy or failing.
- primary_sources:
  - `research/sources/docs/src_doc_0e4ad93cb5ef/artifact.txt`
  - `research/sources/docs/src_doc_bfba858067cc/artifact.txt`
  - `research/sources/docs/src_doc_eafa6e2f9f22/artifact.txt`
  - `research/sources/docs/src_doc_31348971d5a0/artifact.txt`
  - `research/sources/docs/src_doc_bec8b9457702/artifact.txt`
  - `research/sources/papers/papers_text/2603.05344.txt`
  - `research/sources/papers/papers_text/2603.01548.txt`
  - `research/sources/papers/papers_text/2603.01620.txt`
  - `research/sources/papers/papers_text/2603.11495.txt`
  - `research/sources/papers/papers_text/src_pap_d4370863a7e0.txt`
- secondary_sources:
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
- coverage_used:
  - `research/sources/docs/src_doc_0e4ad93cb5ef/artifact.txt`
  - `research/sources/docs/src_doc_bfba858067cc/artifact.txt`
  - `research/sources/docs/src_doc_eafa6e2f9f22/artifact.txt`
  - `research/sources/docs/src_doc_31348971d5a0/artifact.txt`
  - `research/sources/docs/src_doc_bec8b9457702/artifact.txt`
  - `research/sources/papers/papers_text/2603.05344.txt`
  - `research/sources/papers/papers_text/2603.01548.txt`
  - `research/sources/papers/papers_text/2603.01620.txt`
  - `research/sources/papers/papers_text/2603.11495.txt`
  - `research/sources/papers/papers_text/src_pap_d4370863a7e0.txt`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
- coverage_not_yet_used:
  - `research/sources/docs/src_doc_695f1b9755d4/artifact.txt`
  - `research/sources/docs/src_doc_78e1a708df4a/artifact.txt`
  - `research/sources/papers/papers_text/2603.00324.txt`
  - `research/sources/papers/papers_text/2603.03329.txt`
  - `research/sources/papers/papers_text/2602.07274.txt`
- evidence_classes_touched:
  - docs
  - papers
  - prior_wave_synthesis
  - coverage_register
- priority_sources_not_yet_read:
  - `research/sources/docs/src_doc_695f1b9755d4/artifact.txt`
  - `research/sources/docs/src_doc_78e1a708df4a/artifact.txt`
  - `research/sources/papers/papers_text/2603.00324.txt`
- formal_claims:
  - |
    Claim 1
    Observation: OpenAI function-calling docs and MCP tools spec both formalize tool interfaces as explicit schemas, including input shape, optional output schema, and structured error channels.
    Inference: The formal baseline for tool gateways is typed contract surfaces, not free-form tool strings.
    Confidence: high
    Evidence: `research/sources/docs/src_doc_0e4ad93cb5ef/artifact.txt`, `research/sources/docs/src_doc_bfba858067cc/artifact.txt`
  - |
    Claim 2
    Observation: OpenAI function-calling and Anthropic advanced-tool-use docs both elevate deferred loading/search (`tool_search`, `defer_loading`) to handle large tool libraries.
    Inference: Formal doctrine treats tool discovery as a first-class mechanism because loading all tools upfront is context-destructive.
    Confidence: high
    Evidence: `research/sources/docs/src_doc_0e4ad93cb5ef/artifact.txt`, `research/sources/docs/src_doc_eafa6e2f9f22/artifact.txt`
  - |
    Claim 3
    Observation: Anthropic code-execution-with-MCP and advanced-tool-use docs specify programmatic tool orchestration in code execution environments, where intermediate tool outputs can stay outside model context.
    Inference: Formal tool gateway design is bifurcating into (a) direct tool-calling and (b) code-mediated orchestration, with the latter aimed at context efficiency and multi-step control flow.
    Confidence: high
    Evidence: `research/sources/docs/src_doc_31348971d5a0/artifact.txt`, `research/sources/docs/src_doc_eafa6e2f9f22/artifact.txt`
  - |
    Claim 4
    Observation: OPENDEV, Tool-DC, ToolRLA, and graph-routing papers all treat tool-use reliability as a decomposition problem (schema checks, deterministic rerouting, multiplicative correctness penalties, or explicit recovery loops) rather than pure single-pass prompting.
    Inference: Formal literature supports a mechanism family where tool gateway reliability is enforced via external validators/routing logic, not left solely to LLM deliberation.
    Confidence: medium
    Evidence: `research/sources/papers/papers_text/2603.05344.txt`, `research/sources/papers/papers_text/2603.11495.txt`, `research/sources/papers/papers_text/2603.01620.txt`, `research/sources/papers/papers_text/2603.01548.txt`
    Weakener: These are heterogeneous methods with mixed external validity; not all are coding-agent production studies.
  - |
    Claim 5
    Observation: MCPAgentBench explicitly builds local/sandboxed MCP evaluation with distractor tools and protocol-consistent tool definitions.
    Inference: Formal benchmark pressure is shifting from raw task completion to tool-selection discrimination under distractors and stable local gateway conditions.
    Confidence: medium
    Evidence: `research/sources/papers/papers_text/src_pap_d4370863a7e0.txt`
    Weakener: This is benchmark-focused and does not itself prove production robustness.
- benchmark_or_definition_notes:
  - `src_doc_bfba858067cc` is the strongest protocol-definition source in this pass for MCP tool semantics and schema surfaces.
  - `src_pap_d4370863a7e0` is the clearest formal benchmark-definition source for MCP tool-selection under sandboxed distractor pressure.
  - `2603.11495` contributes a clear Try-Check-Retry definition where schema consistency checking is a named stage.
- mechanism_relevance:
  - Supports Wave 05 mechanism candidates for `typed tool contracts`, `deferred tool discovery`, and `externalized tool reliability controls`.
  - Sharpens the distinction between tool-gateway architecture and generic planning rhetoric.
- failure_relevance:
  - Formal sources converge on failure modes of wrong-tool choice, hallucinated tools, malformed arguments, and context blow-up from oversized tool inventories.
  - Formal coverage is weaker on file-path/cwd corruption than on schema/routing errors.
- eval_relevance:
  - Strongly relevant for future eval implications that need distractor-heavy tool sets, protocol-valid schemas, and explicit selection-validity metrics.
- contradictions:
  - Formal docs and papers strongly favor rich gateway stacks (search, deferred loading, code execution, routing), but accepted Wave 04 carry-forward cautions still require preserving minimal-sufficient artifact-first baselines and avoiding prestige overread.
  - Formal tool-gateway sophistication does not by itself establish cross-family behavior in trajectories.
  - Evidence: `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`, `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
- confidence_notes:
  - High confidence in schema/deferred-discovery/programmatic-calling claims due convergent official docs and multiple papers.
  - Medium confidence in deterministic-routing generalization as a cross-system family because supporting papers are method-diverse and partly prototype-centric.
- open_questions:
  - Which formal sources best quantify tradeoffs between deferred discovery latency and selection quality in real coding trajectories?
  - How often do schema-first gateways materially reduce wrong-tool failures in long-horizon terminal tasks versus only benchmark settings?
- downstream_use:
  - Use this theme dossier to pressure Wave 05 mechanism cards around tool gateways and avoid collapsing gateway design into generic execution-control language.
- wave_01_literature_pressure_update_2026_04_10:
  - context: `failure_taxonomy` Wave 01 (`execution_control_and_terminal_failures`) formal-lane carry-forward.
  - observation: Formal tool-gateway sources converge on schema-valid contracts, actionable tool errors, and discovery/routing controls as primary safeguards against terminal/tool misuse.
  - inference: Wave 01 failure attribution should keep `gateway-contract failures` (wrong tool, malformed args, stale discovery) distinct from generic planning/model failures.
  - confidence: high
  - evidence_paths:
    - `research/sources/docs/src_doc_0e4ad93cb5ef/artifact.txt`
    - `research/sources/docs/src_doc_bfba858067cc/artifact.txt`
    - `research/sources/docs/src_doc_78e1a708df4a/artifact.txt`
    - `research/sources/docs/src_doc_eafa6e2f9f22/artifact.txt`
    - `research/sources/docs/src_doc_31348971d5a0/artifact.txt`
    - `research/sources/papers/papers_text/src_pap_d4370863a7e0.txt`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/literature_papers_docs_analyst.md`
- wave_01_execution_control_and_terminal_failures_update:
  - observations:
    - Wave 01 source evidence reinforces that tool gateway shape is an execution-control mechanism, not only a productivity choice (`local_shell` direct shell coupling in DeepAgents; process-tool lifecycle controls in KIRA).
    - Trajectory pressure shows that tool correctness is insufficient without gateway-aware verification and cleanup (headless-terminal and cancel-async-tasks families).
  - inferences:
    - failure taxonomy should treat `tool invocation path` and `tool lifecycle governance` as separate failure axes.
    - verifier omission risk increases when tool calls are accepted as completion evidence without postcondition checks.
  - confidence:
    - high for source-backed gateway/control split
    - medium for cross-family prevalence outside sampled Wave 01 families
  - evidence_paths:
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/local_shell.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_tools.py`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`
