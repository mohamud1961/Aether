LITERATURE_PAPERS_DOCS_OUTPUT
- artifact: mechanism_map
- role: literature/papers/docs analyst

- preflight_scope_confirmed: |
    yes. This is the formal-source lane for `mechanism_map`. It stays within:
    - papers: `research/sources/papers/`
    - docs: `research/sources/docs/`
    - formal design/docs embedded in mirrored repos when they are part of the source tree (e.g., captured repo READMEs).
    It does not use informal/blog/tweets/issues/postmortems as evidence, even if those were stored under `research/sources/docs/`.

- preflight_planned_read_order: |
    1. Packet + protocol + checklist:
       - `tracking/collab/stage_02_synthesis/mechanism_map/brief.md`
       - `tracking/collab/stage_02_synthesis/mechanism_map/inputs/wave_01_launch.md`
       - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
       - `tracking/collab/stage_02_synthesis/adjudication/DEEP_SYNTHESIS_V1_AUDIT_CHECKLIST.md`
    2. In-scope harness docs for mechanism intent:
       - Terminus-KIRA README: `research/sources/codebases/KIRA/README.md`
       - BigAI/TongAgents translated docs: `research/sources/docs/bigai/translated/*.md`
       - OpenHands agent architecture: `research/sources/docs/src_doc_f00f2b63fb7b/artifact.txt`
    3. Tool gateway + sandbox/security + deterministic-control docs:
       - OpenAI function calling + tool search: `research/sources/docs/src_doc_384400cfab11/artifact.txt`
       - OpenAI MCP docs: `research/sources/docs/src_doc_bec8b9457702/artifact.txt`
       - MCP spec overview: `research/sources/docs/src_doc_f6a1b2c3d4e5/artifact.txt`
       - Codex security/approvals/sandboxing: `research/sources/docs/src_doc_5438a826fc4c/artifact.txt`
       - Claude Code subagents + hooks docs: `research/sources/docs/src_doc_7dc93e85c023/artifact.txt`,
         `research/sources/docs/src_doc_e843f93261f0/artifact.txt`
       - Bedrock strict tool use: `research/sources/docs/src_doc_4d5e6f1a2b3c/artifact.txt`
    4. Context/caching docs:
       - Gemini long context + caching: `research/sources/docs/src_doc_a61fba9aae97/artifact.txt`,
         `research/sources/docs/src_doc_f05f01ee79e9/artifact.txt`
    5. Formal eval/benchmark definition anchors (as available in this environment):
       - SWE-rebench abstract page capture: `research/sources/papers/src_pap_b4d59442a63d/artifact.txt`
       - TerminalBench paper capture metadata (PDF exists but not read in this lane): `research/sources/papers/src_pap_f6aa42bfdc1a/capture.json`

- preflight_critical_sources_selected:
  - Terminus-KIRA harness intent + concrete mechanism claims:
    - `research/sources/codebases/KIRA/README.md`
  - BigAI/TongAgents harness intent + plan/execute + tool/MCP support:
    - `research/sources/docs/bigai/translated/sdk_agent_core.md`
    - `research/sources/docs/bigai/translated/sdk_tools_mcp.md`
    - `research/sources/docs/bigai/translated/sdk_workflow.md`
    - `research/sources/docs/bigai/translated/architecture_plan_execute.md`
    - `research/sources/docs/bigai/translated/framework_multi_agent.md`
  - OpenHands agent loop structure (step loop, event log, condenser, security analyzer, action confirmation):
    - `research/sources/docs/src_doc_f00f2b63fb7b/artifact.txt`
  - Tool gateway / protocol constraints / security surfaces:
    - `research/sources/docs/src_doc_384400cfab11/artifact.txt`
    - `research/sources/docs/src_doc_bec8b9457702/artifact.txt`
    - `research/sources/docs/src_doc_f6a1b2c3d4e5/artifact.txt`
    - `research/sources/docs/src_doc_5438a826fc4c/artifact.txt`
    - `research/sources/docs/src_doc_4d5e6f1a2b3c/artifact.txt`
  - Deterministic-control mechanisms (subagents, hooks):
    - `research/sources/docs/src_doc_7dc93e85c023/artifact.txt`
    - `research/sources/docs/src_doc_e843f93261f0/artifact.txt`
  - Eval freshness/contamination concerns (formal benchmark pipeline, abstract-level evidence):
    - `research/sources/papers/src_pap_b4d59442a63d/artifact.txt`

- preflight_coverage_risks:
  - Paper PDF access is limited (no local PDF-to-text tooling). For most PDFs, this lane can only cite capture metadata (title/URL/hash), not content. This weakens any attempt to use papers as primary evidence for mechanism definitions.
  - Some captured docs are partial (cookie/nav-only captures). Example: `research/sources/docs/src_doc_c3d4e5f6a1b2/artifact.txt` is not content-bearing enough to cite for claims.
  - Product/provider docs express intended mechanisms and contracts; they do not, by themselves, prove those mechanisms were present in the observed trajectories or in the mirrored source code.

- preflight_likely_blind_spots:
  - TerminalBench paper contract details (task rules, environment contract, scoring, anti-cheat) are not extracted in this lane in wave 1 (PDF not text-readable here).
  - Formal benchmark-rigor prescriptions from `Establishing Best Practices in Building Rigorous Agentic Benchmarks` are not extracted in this lane in wave 1 (PDF not text-readable here).
  - Formal docs embedded in other mirrored codebases (DeepAgents, a-evolve, etc.) were not comprehensively scanned in this lane.

- preflight_blockers: none.

- coverage_used:
  - packet/protocol/prompts:
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
    - `tracking/collab/stage_02_synthesis/adjudication/DEEP_SYNTHESIS_V1_AUDIT_CHECKLIST.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/brief.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/inputs/wave_01_launch.md`
    - `prompts/deep_synthesis_shared_policy_prompt.md`
    - `prompts/deep_synthesis_literature_papers_docs_analyst_prompt.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/README.md`
  - formal docs (OSS + provider + specs):
    - `research/sources/codebases/KIRA/README.md`
    - `research/sources/docs/bigai/translated/sdk_agent_core.md`
    - `research/sources/docs/bigai/translated/sdk_tools_mcp.md`
    - `research/sources/docs/bigai/translated/sdk_workflow.md`
    - `research/sources/docs/bigai/translated/architecture_plan_execute.md`
    - `research/sources/docs/bigai/translated/framework_multi_agent.md`
    - `research/sources/docs/src_doc_f00f2b63fb7b/artifact.txt`
    - `research/sources/docs/src_doc_384400cfab11/artifact.txt`
    - `research/sources/docs/src_doc_bec8b9457702/artifact.txt`
    - `research/sources/docs/src_doc_f6a1b2c3d4e5/artifact.txt`
    - `research/sources/docs/src_doc_5438a826fc4c/artifact.txt`
    - `research/sources/docs/src_doc_7dc93e85c023/artifact.txt`
    - `research/sources/docs/src_doc_e843f93261f0/artifact.txt`
    - `research/sources/docs/src_doc_4d5e6f1a2b3c/artifact.txt`
    - `research/sources/docs/src_doc_a61fba9aae97/artifact.txt`
    - `research/sources/docs/src_doc_f05f01ee79e9/artifact.txt`
    - `research/sources/docs/src_doc_e7c64f113146/artifact.txt`
    - `research/sources/docs/src_doc_70f56cd7eee7/artifact.txt`
  - papers (content-bearing abstract page capture only):
    - `research/sources/papers/src_pap_b4d59442a63d/artifact.txt`
    - `research/sources/papers/src_pap_b4d59442a63d/capture.json`
  - papers (metadata-only anchors):
    - `research/sources/papers/src_pap_f6aa42bfdc1a/capture.json`
    - `research/sources/papers/src_pap_dd4ca3841fb4/capture.json`
    - `research/sources/papers/src_pap_c5f42ff16ea3/capture.json`

- coverage_not_yet_used:
  - paper PDFs (not text-extracted in this lane): `research/sources/papers/src_pap_*/artifact.pdf`, plus the bulk set under `research/sources/papers/*.pdf`
  - docs in scope but not used here: `research/sources/docs/src_doc_*/artifact.*` (many captures; triage required to keep the formal lane clean)
  - BigAI raw docs: `research/sources/docs/bigai/raw/*.txt` (only translated summaries were read in this wave)

- evidence_classes_touched:
  - docs
  - papers

- priority_sources_not_yet_read:
  - TerminalBench paper content: `research/sources/papers/src_pap_f6aa42bfdc1a/artifact.pdf` (and duplicate capture `src_pap_dd4ca3841fb4/artifact.pdf`)
  - Agentic benchmark rigor paper content: `research/sources/papers/src_pap_c5f42ff16ea3/artifact.pdf`
  - Paper cluster that looks directly mechanism-relevant by title metadata, but not read here: `research/sources/papers/2510.04618.pdf`, `research/sources/papers/2510.11967.pdf`, `research/sources/papers/2512.05470.pdf`, `research/sources/papers/2512.13564.pdf`, `research/sources/papers/2603.03329.pdf`

- formal_claims:
  - claim: Terminus-KIRA explicitly frames itself as a minimal harness delta on top of Terminus 2 for TerminalBench, emphasizing tool calling, multimodal support, execution optimization, and completion verification as primary levers.
    - evidence: `research/sources/codebases/KIRA/README.md`
    - confidence: high (doc-claim)
  - claim: Terminus-KIRA documents a specific "native tool calling" mechanism: replace ICL JSON/XML parsing with LLM `tools` parameter, and route completion through a dedicated `task_complete` tool (with additional completion verification).
    - evidence: `research/sources/codebases/KIRA/README.md`
    - confidence: medium (doc-claim; requires code/trajectory reconciliation)
  - claim: Terminus-KIRA documents a concrete execution-control optimization: marker-based polling via appending an `echo '__CMDEND__<seq>__'` marker to detect command completion early.
    - evidence: `research/sources/codebases/KIRA/README.md`
    - confidence: medium (doc-claim; requires code/trajectory reconciliation)
  - claim: BigAI/TongAgents docs assert an explicit plan-execute (and optional verify/reflect/replan) decomposition where the Planner performs reasoning/strategy and does not directly call tools; the Executor performs tool invocations and yields observations.
    - evidence: `research/sources/docs/bigai/translated/architecture_plan_execute.md`
    - confidence: high (doc-claim)
  - claim: BigAI/TongAgents docs describe Tools as a first-class bridge to external systems and describe a Tool 2.0 architecture with `ToolManager` + `MCPClient`, plus schema generation/validation and protocol-level retry/timeout.
    - evidence: `research/sources/docs/bigai/translated/sdk_tools_mcp.md`
    - confidence: high (doc-claim)
  - claim: BigAI/TongAgents docs describe a workflow-graph harness mechanism (nodes/edges/nesting) and an environment/dispatcher concept (`WorkFlowEnv`) that centralizes lifecycle/tool/MCP dispatch around a workflow runtime.
    - evidence: `research/sources/docs/bigai/translated/sdk_workflow.md`
    - confidence: medium (doc-claim; precise semantics require code review)
  - claim: OpenHands docs present a stateless, event-driven agent loop: a `step()` processes one cycle; it can request condensation when token limits are hit; it parses model output into action/message events; tools execute via action-observation; actions can require confirmation; and a security analyzer evaluates action risk.
    - evidence: `research/sources/docs/src_doc_f00f2b63fb7b/artifact.txt`
    - confidence: high (doc-claim)
  - claim: Claude Code docs define subagents as an explicit harness mechanism for context isolation: each subagent runs with its own context window, custom system prompt, tool access restrictions, and independent permissions; subagents help preserve main-context by moving exploration/parallel work out-of-band.
    - evidence: `research/sources/docs/src_doc_7dc93e85c023/artifact.txt`
    - confidence: high (doc-claim)
  - claim: Claude Code docs define hooks as deterministic lifecycle callbacks executing user-defined shell commands at specific events (e.g., `PreToolUse`, `PostToolUse`, `PermissionRequest`, `Stop`), enabling enforcement/automation that always happens rather than relying on model choice; docs also note non-determinism hazards when multiple hooks rewrite the same input.
    - evidence: `research/sources/docs/src_doc_e843f93261f0/artifact.txt`
    - confidence: high (doc-claim)
  - claim: OpenAI function calling docs support (a) tool definitions via JSON Schema, (b) tool search to defer rarely-used tools and load them on demand, and (c) grammar/regex-constrained custom tools to bound outputs (a strict-output harness primitive).
    - evidence: `research/sources/docs/src_doc_384400cfab11/artifact.txt`
    - confidence: high (doc-claim)
  - claim: OpenAI MCP docs include a substantial security discussion (prompt injection, privacy overreach via tool parameters, write-action confirmations, trust boundaries), implying harnesses need explicit tool classification and approval/confirmation surfaces.
    - evidence: `research/sources/docs/src_doc_bec8b9457702/artifact.txt`
    - confidence: high (doc-claim)
  - claim: MCP spec overview describes MCP as an open protocol for connecting AI apps/agents to data sources, tools, and workflows (standardized connector surface).
    - evidence: `research/sources/docs/src_doc_f6a1b2c3d4e5/artifact.txt`
    - confidence: high (doc-claim)
  - claim: Codex security docs describe a two-layer safety control surface (sandbox mode + approvals), with default network-off and OS-enforced sandboxing (workspace-scoped restrictions) and explicit user approvals for risky operations.
    - evidence: `research/sources/docs/src_doc_5438a826fc4c/artifact.txt`
    - confidence: high (doc-claim)
  - claim: Bedrock strict tool use docs spell out the client-side tool calling pattern (model proposes tool call; application executes tool and returns results), and include examples of "memory" and "tasks" tools that persist within a conversation (including a LIFO task stack), which are explicit harness submechanisms (session-scoped state stores).
    - evidence: `research/sources/docs/src_doc_4d5e6f1a2b3c/artifact.txt`
    - confidence: medium (doc-claim; doc is long and multi-topic, so per-feature reconciliation is needed)
  - claim: Gemini docs define explicit and implicit context caching, include concrete thresholds and TTL semantics, and discuss long-context use cases (including agentic workflows) alongside limitations for multi-needle retrieval (accuracy drops when many distinct facts must be retrieved).
    - evidence: `research/sources/docs/src_doc_f05f01ee79e9/artifact.txt`, `research/sources/docs/src_doc_a61fba9aae97/artifact.txt`
    - confidence: high (doc-claim)
  - claim: SWE-rebench describes a pipeline to continuously extract interactive SWE tasks from GitHub repositories, build a large interactive dataset, and generate contamination-free evaluation tasks; this implies an eval-harness mechanism family around freshness + decontamination + continuous task generation.
    - evidence: `research/sources/papers/src_pap_b4d59442a63d/artifact.txt`
    - confidence: medium (abstract-only)
  - claim: The GPT-5.3-Codex system card references TerminalBench as one proxy evaluation for measuring long-range autonomy (LRA), and also describes sandboxed agent execution environments and network-off defaults for agent operation.
    - evidence: `research/sources/docs/src_doc_70f56cd7eee7/artifact.txt`
    - confidence: medium (doc-claim; not a TerminalBench contract definition)

- terminology_and_definition_notes:
  - "Harness" boundary (operational decomposition, not rhetoric):
    - OpenHands decomposes "agent system" responsibilities into loop orchestration, tool execution, context management (condensers), and security validation as explicit components around the model.
    - evidence: `research/sources/docs/src_doc_f00f2b63fb7b/artifact.txt`
  - "Planner / Executor / Verification loop" (BigAI/TongAgents):
    - Planner outputs a plan; Executor executes tools; Planner can reflect/replan based on observations.
    - evidence: `research/sources/docs/bigai/translated/architecture_plan_execute.md`
  - "Subagent" (Claude Code):
    - Isolated context window + tool restrictions + independent permission mode; used for specialization and context preservation.
    - evidence: `research/sources/docs/src_doc_7dc93e85c023/artifact.txt`
  - "Hook" (Claude Code):
    - Deterministic lifecycle callbacks that can block/modify tool calls and inject context.
    - evidence: `research/sources/docs/src_doc_e843f93261f0/artifact.txt`
  - "MCP" (OpenAI + MCP site + BigAI):
    - Open protocol for connecting AI apps to tools/data/workflows.
    - evidence: `research/sources/docs/src_doc_bec8b9457702/artifact.txt`, `research/sources/docs/src_doc_f6a1b2c3d4e5/artifact.txt`, `research/sources/docs/bigai/translated/sdk_tools_mcp.md`
  - "AGENTS.md" (open spec):
    - A file-format convention for agent-specific repository instructions, with nearest-file precedence (nested AGENTS) as a mechanism for scoped policy.
    - evidence: `research/sources/docs/src_doc_e7c64f113146/artifact.txt`

- benchmark_definition_notes:
  - TerminalBench is a formal benchmark paper in-scope (integrity anchor), but its PDF content was not extracted in this wave, so no contract-level benchmark claims are made here.
    - evidence: `research/sources/papers/src_pap_f6aa42bfdc1a/capture.json`, `research/sources/papers/src_pap_dd4ca3841fb4/capture.json`
  - SWE-rebench provides (at abstract-level) a definition of a contamination-aware SWE evaluation pipeline with a continuously refreshed benchmark stream.
    - evidence: `research/sources/papers/src_pap_b4d59442a63d/artifact.txt`

- mechanism_or_failure_support:
  - Tool schema strictness / native tool calling:
    - Strong formal support that "tool calling via schemas/structured interfaces" is an explicit mechanism in multiple ecosystems (OpenAI function calling docs; Terminus-KIRA README; BigAI tool schema generation docs).
    - evidence: `research/sources/docs/src_doc_384400cfab11/artifact.txt`, `research/sources/codebases/KIRA/README.md`, `research/sources/docs/bigai/translated/sdk_tools_mcp.md`
  - Deterministic non-model control loops:
    - Hooks (Claude Code) + security analyzer + confirmation gating (OpenHands) are explicit doc-backed harness mechanisms that sit outside the model.
    - evidence: `research/sources/docs/src_doc_e843f93261f0/artifact.txt`, `research/sources/docs/src_doc_f00f2b63fb7b/artifact.txt`
  - Context scaling mechanisms:
    - Condensers (OpenHands), context caching (Gemini), and prompt caching (Terminus-KIRA doc-claim) are formal mechanism candidates for long-horizon runs.
    - evidence: `research/sources/docs/src_doc_f00f2b63fb7b/artifact.txt`, `research/sources/docs/src_doc_f05f01ee79e9/artifact.txt`, `research/sources/codebases/KIRA/README.md`
  - Multi-agent / decomposition:
    - BigAI plan/execute separation and Claude Code subagents provide two distinct doc-backed decomposition patterns: role-split within one agent loop vs separate subagents with isolated contexts.
    - evidence: `research/sources/docs/bigai/translated/architecture_plan_execute.md`, `research/sources/docs/src_doc_7dc93e85c023/artifact.txt`

- conflicts_with_direct_evidence:
  - Not reconciled in this lane in wave 1 (formal intent only). Required cross-check targets:
    - BigAI: verify whether plan/execute/verify and actor/runtime patterns appear in `research/sources/trajectories/BigAI/` and in `research/analysis/bigai_trace_layer/output/*`.
    - KIRA: verify README claims (marker polling, tool calling, summarization-on-overflow, completion checklist) against `research/sources/codebases/KIRA/` and the Terminus-KIRA trajectories.
    - OpenHands: doc-claim about stateless step loop and condenser behavior should be checked against the captured OpenHands codebase (outside this lane).

- confidence_notes:
  - high confidence means "the doc explicitly claims this mechanism/contract exists".
  - medium/low confidence notes reflect (a) abstract-only paper evidence, (b) missing PDF extraction, or (c) claims that are likely to diverge in implementations and require code/trajectory reconciliation.

- open_questions:
  - Paper-reading process: what project procedure/tooling will be used to read `research/sources/papers/src_pap_*/artifact.pdf` during waves, so TerminalBench and benchmark-rigor contracts can be cited at content level?
  - Subagents vs plan/execute: which decomposition patterns are actually evidenced in TerminalBench trajectories (separate subagents, explicit planner/executor, or monolithic ReAct with tool schemas)?
  - Completion doctrine: how often do doc-claimed completion checks (e.g., Terminus-KIRA "double-confirmation checklist") catch false completion in practice on TerminalBench task families?
  - Security/control-plane: where do prompt-injection and tool-parameter privacy risks (OpenAI MCP docs) show up in real CLI task trajectories, and what minimal harness controls mitigate them without over-constraining?

- next_hand_off_target: |
    `tracking/collab/stage_02_synthesis/mechanism_map/outputs/contradiction_analyst.md`,
    then principal steward synthesis in `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/principal_synthesis.md`.

