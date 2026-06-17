LITERATURE_PAPERS_DOCS_OUTPUT
- artifact: `mechanism_map`
- role: `literature/papers/docs analyst`
- preflight_scope_confirmed:
  - This is a vertical mechanism-domain wave, not a source-only pass.
  - Trajectory/failure remains the primary empirical anchor for the wave; this role only supplies the formal-source lane that should pressure, sharpen, or weaken later cross-lane claims.
  - The wave focus is execution control and terminal grounding across PTY control, interrupts, replanning, stop rules, and repo-state-safe execution.
- preflight_planned_read_order:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/brief.md` plus carry-forward synthesis surfaces to confirm domain, scope, and required contradiction pressure.
  - Keep the wave's primary empirical anchors visible for later reconciliation: `research/sources/trajectories/deepagents/headless-terminal/`, `research/sources/trajectories/terminus-kira/headless-terminal/`, `research/sources/trajectories/BigAI/headless-terminal/`, `research/sources/trajectories/deepagents/cancel-async-tasks/`, `research/sources/trajectories/terminus-kira/cancel-async-tasks/`, `research/sources/trajectories/BigAI/cancel-async-tasks/`, `research/sources/trajectories/deepagents/break-filter-js-from-html/`, `research/sources/trajectories/terminus-kira/git-multibranch/`.
  - Read formal benchmark and terminal-agent anchors first: Terminal-Bench, OPENDEV.
  - Read official docs and protocol/spec surfaces next: Codex agent loop, shell/skills/compaction, MCP tools spec, BigAI/TongAgent translated docs, Anthropic advanced tool use.
  - Read orchestration/control papers last to sharpen planner/executor, verification, and stop-rule terminology without letting them outrank terminal-specific direct evidence.
  - Leave informal/issues and eval sidecar pressure to sibling roles unless a formal benchmark contract becomes load-bearing.
- preflight_critical_sources_selected:
  - Critical trajectory slices selected for later reconciliation: `research/sources/trajectories/deepagents/headless-terminal/`, `research/sources/trajectories/terminus-kira/headless-terminal/`, `research/sources/trajectories/BigAI/headless-terminal/`, `research/sources/trajectories/deepagents/cancel-async-tasks/`, `research/sources/trajectories/terminus-kira/cancel-async-tasks/`, `research/sources/trajectories/BigAI/cancel-async-tasks/`, `research/sources/trajectories/deepagents/break-filter-js-from-html/`, `research/sources/trajectories/terminus-kira/git-multibranch/`.
  - Critical source systems selected for later reconciliation: `research/sources/codebases/deepagents/`, `research/sources/codebases/KIRA/`, `research/sources/codebases/quarantine/claw-code/`, `research/sources/codebases/a-evolve/`, `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`, local `blocks/`, `runner/`, and `evals/`.
  - Formal benchmark and mechanism anchors selected for this pass: `research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.{txt,meta.json}`, `research/sources/papers/papers_text/src_pap_35d84f1edd93.{txt,meta.json}`, `research/sources/papers/papers_text/src_pap_9a7e75663b9d.{txt,meta.json}`, `research/sources/papers/papers_text/src_pap_74adc431af95.{txt,meta.json}`, `research/sources/papers/papers_text/src_pap_c5f42ff16ea3.{txt,meta.json}`, `research/sources/docs/src_doc_7ab6c0af53c0/{artifact.txt,capture.json}`, `research/sources/docs/src_doc_64510e405cf6/{artifact.txt,capture.json}`, `research/sources/docs/src_doc_78e1a708df4a/{artifact.txt,capture.json}`, `research/sources/docs/src_doc_eafa6e2f9f22/{artifact.txt,capture.json}`, `research/sources/docs/bigai/translated/architecture_plan_execute.md`, `research/sources/docs/bigai/translated/sdk_agent_core.md`, `research/sources/docs/bigai/translated/sdk_workflow.md`.
  - Contradiction-pressure sources selected: `research/sources/docs/src_doc_78e1a708df4a/artifact.txt` for human-in-loop tool-use expectations, `research/sources/docs/src_doc_7ab6c0af53c0/artifact.txt` for simple single-loop execution control, `research/sources/docs/src_doc_eafa6e2f9f22/artifact.txt` for dynamic tool discovery/programmatic orchestration, `research/sources/docs/bigai/translated/architecture_plan_execute.md` for planner/executor claims, `research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.txt` for outcome-driven benchmark contract.
  - Minimal-sufficient contender to keep visible: the Codex-style single agent loop with shell tools, prompt-prefix preservation, compaction, and assistant-message termination in `research/sources/docs/src_doc_7ab6c0af53c0/artifact.txt`; this should remain visible against more elaborate planner/executor or DAG orchestration architectures.
- preflight_coverage_risks:
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` is empty in this checkout, so normal organizer routing support is absent for this pass.
  - `research/sources/papers/papers_text/src_pap_163afe88846b.meta.json` identifies "Verifiable Agent Loops: Formally Modeling Autonomous Terminal Interactions", but `research/sources/papers/papers_text/src_pap_163afe88846b.txt` extracts an unrelated mathematics paper; this capture mismatch makes that paper unusable for this pass.
  - `research/sources/papers/papers_text/src_pap_c5f42ff16ea3.meta.json` marks the benchmark-best-practices slide deck as `usable_with_caveats` with low text density.
  - BigAI formal documentation is translated provider documentation, not mirrored source; any BigAI mechanism claim remains provider-stated intent until trajectory/source lanes confirm it.
  - Repo-state-safe branching and cleanup are only partially formalized in the sources read here; that mechanism family will remain source/trajectory-heavy.
- preflight_likely_blind_spots:
  - Exact runtime behavior when providers' docs overstate planning, verification, or approval usage.
  - PTY, interrupt, and stuck-process handling in systems whose formal documentation is sparse or absent.
  - Formal verifier/completion-contract literature beyond the Terminal-Bench contract and the low-quality benchmark-rigor slide deck.
  - Long-tail formal sources not yet read that may pressure context or benchmark interpretations: TermiGen, MCPAgentBench, DeepPlanning, Efficient Benchmarking of AI Agents.
- preflight_blockers:
  - none
- coverage_used:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/brief.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_01_exploratory_anchor/synthesis/principal_synthesis.md`
  - `tracking/collab/stage_02_synthesis/tracing_readiness/outputs/tracing_readiness.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/README.md`
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`
  - `research/sources/papers/pdf_papers/INDEX.md`
  - `research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.{txt,meta.json}`
  - `research/sources/papers/papers_text/src_pap_35d84f1edd93.{txt,meta.json}`
  - `research/sources/papers/papers_text/src_pap_163afe88846b.{txt,meta.json}`
  - `research/sources/papers/papers_text/src_pap_9a7e75663b9d.{txt,meta.json}`
  - `research/sources/papers/papers_text/src_pap_74adc431af95.{txt,meta.json}`
  - `research/sources/papers/papers_text/src_pap_c5f42ff16ea3.{txt,meta.json}`
  - `research/sources/docs/src_doc_64510e405cf6/{artifact.txt,capture.json}`
  - `research/sources/docs/src_doc_7ab6c0af53c0/{artifact.txt,capture.json}`
  - `research/sources/docs/src_doc_78e1a708df4a/{artifact.txt,capture.json}`
  - `research/sources/docs/src_doc_eafa6e2f9f22/{artifact.txt,capture.json}`
  - `research/sources/docs/bigai/translated/architecture_plan_execute.md`
  - `research/sources/docs/bigai/translated/sdk_agent_core.md`
  - `research/sources/docs/bigai/translated/sdk_workflow.md`
- coverage_not_yet_used:
  - `research/sources/papers/papers_text/2602.07274.{txt,meta.json}`
  - `research/sources/papers/papers_text/src_pap_d4370863a7e0.{txt,meta.json}`
  - `research/sources/papers/papers_text/src_pap_8c2cb08d2c57.{txt,meta.json}`
  - `research/sources/papers/papers_text/src_pap_70b31c72af76.{txt,meta.json}`
  - `research/sources/docs/bigai/translated/framework_multi_agent.md`
  - `research/sources/docs/bigai/translated/sdk_tools_mcp.md`
  - `research/sources/docs/src_doc_bfba858067cc/{artifact.txt,capture.json}`
- evidence_classes_touched:
  - `papers`
  - `docs`
  - `artifact-wave scaffolding`
  - `coverage surface / organizer surface`
- priority_sources_not_yet_read:
  - `research/sources/papers/papers_text/2602.07274.txt`
  - `research/sources/papers/papers_text/src_pap_d4370863a7e0.txt`
  - `research/sources/papers/papers_text/src_pap_8c2cb08d2c57.txt`
  - `research/sources/papers/papers_text/src_pap_70b31c72af76.txt`
  - `research/sources/docs/bigai/translated/sdk_tools_mcp.md`
- formal_claims:
  - observation: Terminal-Bench formally defines each task as an instruction, Docker image, tests, example/reference solution, and time limit; the tests verify final container state and intentionally do not test the agent's commands or console output. Evidence: `research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.txt`.
    inference: Formal benchmark scoring therefore under-specifies execution-control mechanisms; shell sequencing, PTY handling, interrupts, or repo hygiene may be crucial for success trajectories even though they are not part of the explicit grading contract. Evidence: `research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.txt`.
    confidence: `high`
  - observation: Terminal-Bench still treats terminal interaction as central task structure: agents are expected to explore/manipulate a containerized environment, and the paper explicitly notes tasks such as async job management that require interactive testing and keyboard interrupts. Evidence: `research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.txt`.
    inference: The benchmark contract supports treating PTY and interrupt recovery as real mechanism families rather than incidental implementation detail, even though scoring is outcome-driven. Evidence: `research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.txt`.
    confidence: `high`
  - observation: OPENDEV frames long-running terminal-agent engineering around three recurring burdens: context-window exhaustion, destructive shell safety, and capability extensibility. Its stated architecture combines workload-specialized routing, dual-agent planning/execution separation, lazy tool discovery, adaptive context compaction, event-driven reminders, approval gates, and defense-in-depth safety. Evidence: `research/sources/papers/papers_text/src_pap_35d84f1edd93.txt`.
    inference: In the formal literature lane, execution control is presented as an explicit harness family with multiple independently swappable submechanisms, not merely as a prompt or tool-schema detail. Evidence: `research/sources/papers/papers_text/src_pap_35d84f1edd93.txt`.
    confidence: `high`
  - observation: OPENDEV gives a concrete terminal-control design: background commands are auto-promoted through server detection, executed in PTYs, tracked as tasks, polled for output, killed through process-group termination, and bounded by idle/absolute timeouts and interrupt tokens. Evidence: `research/sources/papers/papers_text/src_pap_35d84f1edd93.txt`.
    inference: Formal terminal-agent design now treats PTY-backed background execution and explicit regain-control mechanisms as first-class control-loop responsibilities, not as optional shell-tool polish. Evidence: `research/sources/papers/papers_text/src_pap_35d84f1edd93.txt`.
    confidence: `high`
  - observation: OPENDEV's stated stop/control logic includes implicit completion, explicit completion tools, capped recovery nudges, iteration safety limits, incomplete-task checks before accepting completion, doom-loop detection, and context-aware reminders to prevent premature stopping. Evidence: `research/sources/papers/papers_text/src_pap_35d84f1edd93.txt`.
    inference: Stop rules in formal terminal-agent work are not a single "done" flag; they are multi-condition control policies coupled to task state, recovery budget, and loop health. Evidence: `research/sources/papers/papers_text/src_pap_35d84f1edd93.txt`.
    confidence: `high`
  - observation: Codex's official agent-loop doc describes a simpler architecture: the model alternates between inference and tool calls until it emits an assistant message; termination is assistant-message completion, while control robustness comes from stable prompt prefixes, compaction, sandbox/permissions instructions, and explicit handling of working-directory or tool-list changes. Evidence: `research/sources/docs/src_doc_7ab6c0af53c0/artifact.txt`.
    inference: A minimal single-loop harness remains a live mechanism contender against planner/executor splits; the formal literature does not force all strong execution-control systems into multi-role orchestration. Evidence: `research/sources/docs/src_doc_7ab6c0af53c0/artifact.txt`.
    confidence: `high`
  - observation: BigAI/TongAgent docs state a Planner -> Executor -> optional verification/reflection cycle, long-running `run` sessions, workflow-level orchestration through `WorkFlowEnv`, and retry on tool validation failure in `ReactAgent` derivatives. Evidence: `research/sources/docs/bigai/translated/architecture_plan_execute.md`, `research/sources/docs/bigai/translated/sdk_agent_core.md`, `research/sources/docs/bigai/translated/sdk_workflow.md`.
    inference: The provider-stated BigAI mechanism surface is compatible with a planner/executor/verification family, but this remains documentation-level intent until direct trajectories or visible source confirm it. Evidence: `research/sources/docs/bigai/translated/architecture_plan_execute.md`, `research/sources/docs/bigai/translated/sdk_agent_core.md`, `research/sources/docs/bigai/translated/sdk_workflow.md`.
    confidence: `medium`
    weakening_factors: `Translated docs only; no mirrored BigAI harness source was read in this pass.`
  - observation: VMAO formalizes a Plan-Execute-Verify-Replan loop with DAG decomposition, dependency-aware parallel execution, orchestration-level completeness checks, adaptive replanning, and stop conditions keyed to completeness, confidence, diminishing returns, max iterations, and token budget. Evidence: `research/sources/papers/papers_text/src_pap_9a7e75663b9d.txt`.
    inference: Formal orchestration research treats verification and termination as control-layer mechanisms in their own right, but mostly in query-decomposition regimes rather than terminal-shell execution regimes. Evidence: `research/sources/papers/papers_text/src_pap_9a7e75663b9d.txt`.
    confidence: `high`
  - observation: Anthropic's advanced-tool-use doc and the multi-tool orchestration survey both frame context bloat, intermediate-result pollution, state consistency, race conditions, and controlled parallel execution as central system problems once agents move from single tool calls to long-horizon orchestration. Evidence: `research/sources/docs/src_doc_eafa6e2f9f22/artifact.txt`, `research/sources/papers/papers_text/src_pap_74adc431af95.txt`.
    inference: Formal sources converge on a cross-system pattern: execution control is increasingly about managing intermediate state and tool topology under bounded context, not just choosing the next action. Evidence: `research/sources/docs/src_doc_eafa6e2f9f22/artifact.txt`, `research/sources/papers/papers_text/src_pap_74adc431af95.txt`.
    confidence: `high`
- terminology_and_definition_notes:
  - `harness` vs `scaffolding`: OPENDEV separates `scaffolding` (assemble prompt/tool/subagent registry before the first prompt) from `harness` (runtime tool dispatch, context management, safety enforcement), which is directly relevant to the artifact's mechanism granularity. Evidence: `research/sources/papers/papers_text/src_pap_35d84f1edd93.txt`.
  - `agent loop`: Codex defines the loop as repeated inference plus tool execution until assistant-message termination, which provides a clean minimal control-loop definition. Evidence: `research/sources/docs/src_doc_7ab6c0af53c0/artifact.txt`.
  - `outcome-driven framework`: Terminal-Bench uses this phrase to mean final-state verification rather than command-trace verification. Evidence: `research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.txt`.
  - `programmatic tool calling`: Anthropic uses this to distinguish code-mediated orchestration from one-inference-per-tool natural-language calling, with the explicit aim of keeping intermediate results out of the model context. Evidence: `research/sources/docs/src_doc_eafa6e2f9f22/artifact.txt`.
  - `WorkFlowEnv`: BigAI uses this as the environment-level manager for workflow lifecycle, tool calls, MCP dispatch, sandbox, and workspace isolation. Evidence: `research/sources/docs/bigai/translated/sdk_workflow.md`.
- benchmark_definition_notes:
  - Terminal-Bench's formal benchmark contract is final-state and test-driven: tasks are interactive and terminal-centric, but scoring intentionally ignores the command stream. Evidence: `research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.txt`.
  - Terminal-Bench explicitly allows agent scaffolds to manipulate the container however they please; this matters because execution-control mechanisms may be benchmark-relevant without being benchmark-visible. Evidence: `research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.txt`.
  - Terminal-Bench includes formal anti-cheat/integrity design pressure, including an adversarial exploit agent and checklist language about preventing shortcut paths. Evidence: `research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.txt`.
  - The benchmark-best-practices slide deck suggests false-success failure modes such as do-nothing agents or grader unreliability, but this source is low-density slide extraction and should be treated as weak support only. Evidence: `research/sources/papers/papers_text/src_pap_c5f42ff16ea3.txt`, `research/sources/papers/papers_text/src_pap_c5f42ff16ea3.meta.json`.
- mechanism_or_failure_support:
  - `PTY and interactive shell control`
    - Strong formal support: OPENDEV's PTY-based background execution, process-group isolation, polling, and kill escalation. Evidence: `research/sources/papers/papers_text/src_pap_35d84f1edd93.txt`.
    - Benchmark relevance support: Terminal-Bench includes real terminal tasks and explicitly mentions interrupt-heavy async job management cases. Evidence: `research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.txt`.
  - `interrupt and stuck-process recovery`
    - Strong formal support: OPENDEV interrupt tokens, idle/absolute timeouts, and process-group kill logic. Evidence: `research/sources/papers/papers_text/src_pap_35d84f1edd93.txt`.
    - Moderate formal support: MCP clients are advised to expose confirmation prompts, timeouts, logging, and actionable tool errors that enable retry/self-correction. Evidence: `research/sources/docs/src_doc_78e1a708df4a/artifact.txt`.
  - `repo-state-safe branching and cleanup`
    - Partial formal support only: OPENDEV's prompt-level git workflow guidance, operation log, rollback framing, and safety layers indicate the family exists, but the read formal sources do not deeply specify multi-branch cleanup or restore-before-done mechanisms. Evidence: `research/sources/papers/papers_text/src_pap_35d84f1edd93.txt`.
    - Formal support strength for this slice is weaker than for PTY/interrupt control and should be source/trajectory-pressured later.
  - `replanning versus direct execution control`
    - Strong formal support for explicit replanning families: OPENDEV Planner subagent, BigAI Planner/Executor docs, and VMAO's verify/replan loop. Evidence: `research/sources/papers/papers_text/src_pap_35d84f1edd93.txt`, `research/sources/docs/bigai/translated/architecture_plan_execute.md`, `research/sources/papers/papers_text/src_pap_9a7e75663b9d.txt`.
    - Strong formal support for simpler direct-execution contender: Codex single loop with compaction and tool-call continuation but no required planning subagent. Evidence: `research/sources/docs/src_doc_7ab6c0af53c0/artifact.txt`.
  - `context pressure and stop rules as control mechanisms`
    - Cross-source support is strong: Codex compaction, OPENDEV adaptive compaction/reminders/doom-loop detection, Anthropic tool search plus programmatic tool calling, and VMAO completeness/resource stop thresholds. Evidence: `research/sources/docs/src_doc_7ab6c0af53c0/artifact.txt`, `research/sources/papers/papers_text/src_pap_35d84f1edd93.txt`, `research/sources/docs/src_doc_eafa6e2f9f22/artifact.txt`, `research/sources/papers/papers_text/src_pap_9a7e75663b9d.txt`.
- conflicts_with_direct_evidence:
  - observation: No hard trajectory/source contradiction was established directly in this pass because the role prioritized formal-source reading and only used wave scaffolding plus tracing-readiness for cross-lane selection.
    inference: This field should be treated as a contradiction-pressure agenda rather than an adjudicated conflict register.
    confidence: `high`
  - observation: Terminal-Bench's formal contract grades final state rather than command stream. Evidence: `research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.txt`.
    inference: If trajectory/source lanes show that PTY handling, interrupt recovery, branch cleanup, or approval behavior materially separate harness families, those differences may be mechanistically real while remaining benchmark-invisible. This is a likely formal-vs-behavior tension to preserve, not smooth over.
    confidence: `high`
  - observation: MCP's tools spec says there should always be a human in the loop with the ability to deny tool invocations, while provider docs in the same corpus emphasize autonomous long-running loops, programmatic tool calling, and on-demand tool discovery. Evidence: `research/sources/docs/src_doc_78e1a708df4a/artifact.txt`, `research/sources/docs/src_doc_7ab6c0af53c0/artifact.txt`, `research/sources/docs/src_doc_eafa6e2f9f22/artifact.txt`.
    inference: Formal sources themselves already expose an autonomy-vs-confirmation tension that direct harness evidence should test concretely.
    confidence: `medium`
    weakening_factors: `The sources are not mutually exclusive; a system can support autonomous execution and still retain confirmation controls.`
  - observation: BigAI docs claim planner/executor/verification structure, but no mirrored BigAI source was read and the wave packet already marks BigAI source as behaviorally reconstructed. Evidence: `research/sources/docs/bigai/translated/architecture_plan_execute.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/brief.md`.
    inference: Any BigAI mechanism claim stronger than "provider-stated intent" remains vulnerable until the trajectory/source lanes either reconcile or reject it.
    confidence: `high`
- confidence_notes:
  - High-confidence formal anchors:
    - `research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.txt`
    - `research/sources/papers/papers_text/src_pap_35d84f1edd93.txt`
    - `research/sources/papers/papers_text/src_pap_9a7e75663b9d.txt`
    - `research/sources/papers/papers_text/src_pap_74adc431af95.txt`
    - `research/sources/docs/src_doc_7ab6c0af53c0/artifact.txt`
    - `research/sources/docs/src_doc_78e1a708df4a/artifact.txt`
  - Medium-confidence surfaces:
    - BigAI translated docs because they are documentation-only, translated, and source-unreconciled.
    - Anthropic advanced-tool-use doc because it is an official provider blog/doc rather than peer-reviewed formal literature, though it is still useful for stated mechanism intent.
  - Low-confidence / caveated surfaces:
    - `research/sources/papers/papers_text/src_pap_c5f42ff16ea3.txt` due low extracted text density and slide-format loss.
    - `research/sources/papers/papers_text/src_pap_163afe88846b.txt` should not be used for execution-control claims at all because the extracted text does not match the recorded paper metadata.
- open_questions:
  - Do the actual `headless-terminal`, `cancel-async-tasks`, and `git-multibranch` trajectories show that simpler single-loop harnesses reach comparable recovery/grounding behavior to explicit planner/executor stacks?
  - How often do observed harnesses actually surface approval/confirmation controls versus silently auto-executing, given the MCP human-in-loop guidance?
  - Is repo-state-safe branching/cleanup mainly a trajectory/source phenomenon because formal literature under-specifies it, or do unread formal sources close that gap?
  - Does BigAI trajectory behavior really exhibit the planner/executor/verification split promised by its docs, or is the documentation more aspirational than operational?
  - Should unread formal sources such as `research/sources/papers/papers_text/2602.07274.txt`, `research/sources/papers/papers_text/src_pap_d4370863a7e0.txt`, and `research/sources/papers/papers_text/src_pap_8c2cb08d2c57.txt` materially change the current judgment about execution control as a cross-system mechanism family?
- next_hand_off_target: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/contradiction_analyst.md`
