INFORMAL_ISSUES_POSTMORTEMS_OUTPUT
- artifact: `mechanism_map`
- role: `informal/issues/postmortems analyst`
- preflight_scope_confirmed: |
    Scope anchor for captured sources: `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json` (247 captured source IDs). I am treating it as the intake integrity anchor, while also keeping organizer-routed non-intake evidence classes in scope (informal markdown notes, issues, postmortems) per `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`.

    This output is restricted to the informal lane (informal notes + issue reports + postmortems) and is not attempting to claim source-backed implementation truth. Any mechanism claim below is framed as: (a) operator claim, (b) issue-reported failure, or (c) plausible harness mechanism implication that must be validated against trajectories and code in other lanes.
- preflight_planned_read_order: |
    1. Packet + policy guardrails (protocol, brief, role prompt).
    2. Highest-signal postmortems about agent harness operation (OpenAI "harness engineering", Codex app; Cursor dynamic context).
    3. High-signal informal notes on context/trace/agent-loop operations (Cursor dynamic context discovery; Cursor cloud agents; Humanlayer "12 factor"; Cognition "agent trace"; OpenAI monitoring).
    4. Issue reports that reveal hard edges and failure pressure on harness mechanisms (context overflow/compaction; resume/crash recovery; state persistence; dependency/tooling issues; security surfaces).
    5. Stop short of "closing loops" that require trajectory or source validation; instead emit explicit contradiction pressure and validation targets for other lanes.
- preflight_critical_sources_selected: |
    Informal:
    - `research/sources/informal/cursor_dynamic_context_discovery.md`
    - `research/sources/informal/cursor_agent_computer_use.md`
    - `research/sources/informal/humanlayer_12_factor_agents.md`
    - `research/sources/informal/cognition_agent_trace.md`
    - `research/sources/informal/openai_monitor_misalignment.md`
    - `research/sources/informal/anthropic_long_running_harness.md` (partial; capture is hard to read cleanly)

    Issues:
    - `research/sources/issues/src_iss_15bd3d2d6a1d/` (context full -> /compact unresponsive after subagents)
    - `research/sources/issues/src_iss_222a58240294/` (/resume crash due to oversized JSONL tool_result lines)
    - `research/sources/issues/src_iss_4c8fe1b50b87/` (thread stuck "thinking" after crash; missing terminal event)
    - `research/sources/issues/src_iss_6bbe542bed6c/` (skill tool ignores `context: fork` + `agent:` frontmatter)
    - `research/sources/issues/src_iss_f44f83f3fbc3/` (unsafe pickle deserialization in state restore)
    - `research/sources/issues/src_iss_677a876a6ea9/` (CLI startup blocked on rg download hang)

    Postmortems:
    - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/` (OpenAI "harness engineering")
    - `research/sources/postmortems/src_pmt_95c4bda555e0/` (OpenAI "introducing the Codex app")
    - `research/sources/postmortems/src_pmt_ca79e818d699/` (OpenAI "eval skills" tips; intersects mechanism via trace+checks notion)
    - `research/sources/postmortems/src_pmt_afc13590bd50/` (AI-RNG "production agent"; low credibility / ad-heavy)
    - `research/sources/postmortems/src_pmt_2c716b81f9a5/` (OpenDev architecture; capture failure / redirect)
- preflight_coverage_risks: |
    - Informal lane is large (102 informal notes, 55 issues, 6 postmortems). This is a first-pass targeted slice, not exhaustive.
    - Several captures are "single-line dumps" (hard to read precisely without preprocessing); Anthropic long-running harness capture in particular appears to include a lot of Next.js payload noise.
    - At least one postmortem capture is unusable (OpenDev redirects to /lander; text is just a newline). Any OpenDev mechanism claims would be speculation until a better capture exists.
    - Some sources appear contaminated or mixed with unrelated content (OpenAI monitoring capture includes extraneous "setup.ps1" planning text near the end). Treat with caution; use only the high-level, non-contaminated parts.
    - Many claims below are operator intent / design narrative, not direct behavior evidence; they must be reconciled with actual trajectories and source.
- preflight_likely_blind_spots: |
    - I did not scan the bulk of `research/sources/informal/*.md` beyond the selected high-signal items.
    - I did not scan the bulk of `research/sources/issues/src_iss_*/` beyond selected high-signal edge-case reports.
    - I did not consult trajectories or code to validate whether these mechanisms are actually present in BigAI/deepagents/terminus-kira behavior. That validation belongs to other lanes + later contradiction review.
- preflight_blockers: |
    None structural for producing a first-pass informal-lane mechanism pressure report. (However, see capture-quality warnings above.)

- coverage_used:
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
  - `tracking/collab/stage_02_synthesis/adjudication/DEEP_SYNTHESIS_V1_AUDIT_CHECKLIST.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/brief.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/decision.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/inputs/wave_01_launch.md`
  - `prompts/deep_synthesis_shared_policy_prompt.md`
  - `prompts/deep_synthesis_informal_issues_postmortems_analyst_prompt.md`
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - `research/sources/informal/cursor_dynamic_context_discovery.md`
  - `research/sources/informal/cursor_agent_computer_use.md`
  - `research/sources/informal/humanlayer_12_factor_agents.md`
  - `research/sources/informal/cognition_agent_trace.md`
  - `research/sources/informal/openai_monitor_misalignment.md`
  - `research/sources/informal/anthropic_long_running_harness.md` (partial via targeted keyword search; capture is noisy)
  - `research/sources/issues/src_iss_15bd3d2d6a1d/capture.json`
  - `research/sources/issues/src_iss_15bd3d2d6a1d/artifact.txt`
  - `research/sources/issues/src_iss_222a58240294/capture.json`
  - `research/sources/issues/src_iss_222a58240294/artifact.txt`
  - `research/sources/issues/src_iss_4c8fe1b50b87/capture.json`
  - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
  - `research/sources/issues/src_iss_6bbe542bed6c/capture.json`
  - `research/sources/issues/src_iss_6bbe542bed6c/artifact.txt`
  - `research/sources/issues/src_iss_f44f83f3fbc3/capture.json`
  - `research/sources/issues/src_iss_f44f83f3fbc3/artifact.txt`
  - `research/sources/issues/src_iss_677a876a6ea9/capture.json`
  - `research/sources/issues/src_iss_677a876a6ea9/artifact.txt`
  - `research/sources/postmortems/src_pmt_2c716b81f9a5/capture.json`
  - `research/sources/postmortems/src_pmt_2c716b81f9a5/artifact.html` (redirect stub)
  - `research/sources/postmortems/src_pmt_2c716b81f9a5/artifact.txt` (empty)
  - `research/sources/postmortems/src_pmt_95c4bda555e0/capture.json`
  - `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt` (targeted snippet extraction)
  - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/capture.json`
  - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt` (targeted snippet extraction)
  - `research/sources/postmortems/src_pmt_ca79e818d699/capture.json`
  - `research/sources/postmortems/src_pmt_ca79e818d699/artifact.txt` (targeted snippet extraction)
  - `research/sources/postmortems/src_pmt_afc13590bd50/capture.json`
  - `research/sources/postmortems/src_pmt_afc13590bd50/artifact.txt` (targeted snippet extraction; low credibility)

- coverage_not_yet_used:
  - `research/sources/informal/*.md` (most)
  - `research/sources/issues/src_iss_*/` (most)
  - `research/sources/postmortems/src_pmt_350e236460b0/*` (Cursor dynamic context discovery duplicate capture; not read directly here)
  - `research/sources/postmortems/src_pmt_*/artifact.html` (most not read; only specific snippets from artifact.txt were used)
- evidence_classes_touched:
  - informal sources
  - issues
  - postmortems
- priority_sources_not_yet_read: |
    Informal (high-signal candidates likely relevant to mechanism extraction):
    - `research/sources/informal/anthropic_long_running_harness.md` (needs a cleaner read; current capture is noisy)
    - `research/sources/informal/cursor_agent_sandboxing.md` (if present; not read in this pass)
    - `research/sources/informal/cursor_building_bugbot.md`
    - Any informal notes directly about TerminalBench-style harness loops, verifier discipline, replay, and anti-cheat

    Issues (mechanism-relevant edges to consider in later pass):
    - `research/sources/issues/src_iss_2da54ef1607a/` (CLAUDE.md instruction violations / multi-agent permission; not read in this pass)
    - Additional `claude-code` issues about session persistence, /resume semantics, terminal lag, Task caching, etc (many were not touched)
    - Additional `codex` issues about persistence/threads/worktrees/sandboxing (many were not touched)

    Postmortems:
    - `research/sources/postmortems/src_pmt_2c716b81f9a5/*` is unusable as captured; if OpenDev architecture is expected to be in-scope, it needs recapture or alternate on-disk evidence

- high_signal_operating_claims: |
    1) File-backed context offloading for long tool outputs (token control without truncation).
       - Claim type: operator design claim.
       - What: instead of truncating large tool outputs (shell/MCP), write output to a file and give the agent tools to `tail`/read portions as needed.
       - Mechanism implication (L4 candidate): "tool output as artifact" + "selective read" + "lossless offload" as a core context-management mechanism.
       - Confidence: medium (credible vendor blog; still needs validation against our trajectories/harness).
       - Evidence: `research/sources/informal/cursor_dynamic_context_discovery.md`.

    2) Compaction quality improvements by treating chat history as a retrievable file, not only summarized inline.
       - Claim type: operator design claim.
       - What: when summarization/compaction triggers, preserve history externally as a file the agent can search to recover details missing from the summary.
       - Mechanism implication: "history-file retrieval" as a context-reset hedge.
       - Confidence: medium.
       - Evidence: `research/sources/informal/cursor_dynamic_context_discovery.md`.

    3) Dynamic tool discovery: store long tool descriptions as files and load on-demand; reduce tool-prompt bloat.
       - Claim type: operator design claim with reported A/B token reduction.
       - What: sync MCP tool descriptions to a folder; put only tool names in static context; agent looks up details when needed; also conveys auth status.
       - Mechanism implication: "tool registry as filesystem" + "on-demand tool schema retrieval".
       - Confidence: medium (numbers are claimed; mechanism is plausible).
       - Evidence: `research/sources/informal/cursor_dynamic_context_discovery.md`.

    4) Treat integrated terminal session logs as files and discover dynamically (grep) rather than injecting full history statically.
       - Claim type: operator design claim.
       - Mechanism implication: "terminal transcript persistence + selective retrieval".
       - Confidence: medium.
       - Evidence: `research/sources/informal/cursor_dynamic_context_discovery.md`.

    5) Sandbox isolation as a scaling mechanism: per-agent isolated VM, plus artifacts (video/screenshots/logs) to validate work.
       - Claim type: operator design claim + workflow narrative.
       - What: cloud agents run in isolated VMs to avoid resource contention; agents test changes and produce artifacts; they rebase/squash, temporarily bypass feature flags for local tests and revert, etc.
       - Mechanism implication: "isolated execution environment" + "artifacted verification" + "human/agent review surface".
       - Confidence: medium (blog narrative; concrete examples).
       - Evidence: `research/sources/informal/cursor_agent_computer_use.md`.

    6) Deterministic prefetch of likely-needed tool outputs can outperform "ask model to decide to fetch tool X" loops.
       - Claim type: operator advice / design philosophy.
       - What: if you know tool X is likely needed, call it deterministically and include results in context to reduce round trips and confusion; frame agent as loop: model chooses next step, deterministic code executes, append results.
       - Mechanism implication: "prefetch policy" and "loop-as-orchestrator" as explicit harness levers; tension with dynamic discovery (below).
       - Confidence: low-to-medium (general advice; not benchmarked here).
       - Evidence: `research/sources/informal/humanlayer_12_factor_agents.md`.

    7) Context resets (new agent + structured handoff) are distinct from compaction; resets can mitigate "context anxiety".
       - Claim type: operator design claim.
       - What: compaction is lossy-in-place; reset gives clean slate but requires strong handoff artifact; claimed necessary for some long tasks.
       - Mechanism implication: "handoff artifacts" + "agent reset orchestration" as a continuity mechanism.
       - Confidence: low in this pass because the local capture is noisy; treat as a lead until read cleanly.
       - Evidence: `research/sources/informal/anthropic_long_running_harness.md` (partial).

    8) Trace capture as a first-class artifact: "context graph" / agent trace pointers to full conversation context.
       - Claim type: operator spec advocacy.
       - What: store an identifier linking code changes to a retrievable conversation/trajectory; avoid embedding full prompts in code; keep PII out; make context retrievable.
       - Mechanism implication: "trace store + pointer" (observability and later reuse) as a harness/workflow mechanism.
       - Confidence: medium.
       - Evidence: `research/sources/informal/cognition_agent_trace.md`.

    9) Monitoring layer over agent actions/reasoning/tool calls (defense-in-depth).
       - Claim type: operator safety system description.
       - What: asynchronous monitoring over full conversations, tool calls, and reasoning; categorize severity; aim to reduce latency toward near-real-time blocking.
       - Mechanism implication: "monitor agent" as a supervising harness layer, distinct from the primary executor.
       - Confidence: medium for the high-level claim; low for details near the end of the capture that appear contaminated.
       - Evidence: `research/sources/informal/openai_monitor_misalignment.md`.

    10) "Repo legibility" as an operating constraint: push context into repo-local versioned artifacts so agents can discover it.
        - Claim type: postmortem operating principle.
        - What: agents only see what is in-repo and discoverable; context in Slack/Docs is "non-existent" to the agent; shift org behavior to make more decisions discoverable.
        - Mechanism implication: "artifact discipline" and "repo as memory substrate".
        - Confidence: medium.
        - Evidence: `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`.

    11) Multi-thread + worktree based parallelism: isolate agent changes and avoid git state conflicts.
        - Claim type: postmortem/product description.
        - What: agents run in separate threads and worktrees; isolate changes; allow multiple agents on same repo without conflicts.
        - Mechanism implication: "per-agent workspace isolation" in harness runtime.
        - Confidence: medium.
        - Evidence: `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt`.

    12) Expose logs/metrics/traces to the agent, per isolated environment, to shift QA burden from humans to agent feedback loops.
        - Claim type: postmortem operating claim.
        - What: wire observability tooling into agent runtime; per-worktree ephemeral stack; agent queries logs/metrics/traces.
        - Mechanism implication: "observability-as-tool" + "agent self-debugging loops".
        - Confidence: medium.
        - Evidence: `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`.

- issue_and_postmortem_findings: |
    A) Context overflow makes compaction unavailable exactly when needed (subagents exacerbate).
       - Finding: repeated use of subagents (Task tool) spikes context to 100%, then `/compact` becomes unresponsive; proposed mitigations: reserve headroom for compaction, summarize subagent outputs, warn on thresholds, auto-compact, emergency compaction mode.
       - Mechanism pressure: "compaction headroom reserve" + "subagent output summarization" + "auto-compact thresholding" should be considered real harness mechanisms (not UX nice-to-haves) because losing compaction collapses long-horizon ability.
       - Confidence: medium (issue report; plausible).
       - Evidence: `research/sources/issues/src_iss_15bd3d2d6a1d/artifact.txt`.

    B) Persisted conversation history can become unrecoverable if tool results are stored as huge JSONL lines.
       - Finding: `/resume` crashes when conversation JSONL contains tool_result lines > ~50KB; root cause described as oversized JSON lines (JSON escaping overhead); proposed mitigations: tool_result truncation with metadata + expand, streaming/lazy parsing, hard limits at write-time.
       - Mechanism pressure: "bounded persistence format" + "lazy loading of tool results" + "store large blobs out-of-band" (file-backed artifacts) are mechanisms, not just implementation details.
       - Confidence: medium (issue report includes concrete sizes).
       - Evidence: `research/sources/issues/src_iss_222a58240294/artifact.txt`.

    C) Crash recovery needs explicit "terminal events" for in-flight turns; otherwise threads get stuck "thinking".
       - Finding: Codex VS Code extension crash during an in-progress turn can leave thread permanently stuck as "thinking" after restart; user reports persisted thread ends with unfinished reasoning event and lacks a terminal marker; workaround: manually append interruption/abort event; suggested fix: reconcile on startup into aborted/interrupted terminal state.
       - Mechanism pressure: "turn finalization / crash reconciliation" and "idempotent turn state machine" are core harness state mechanisms.
       - Confidence: medium.
       - Evidence: `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`.

    D) Skill execution context isolation can be a first-class control plane, but toolchains may ignore it.
       - Finding: feature request: invoking a skill via Skill tool ignores `context: fork` and `agent:` frontmatter; expected: run in a forked subagent context (keep exploration out of main thread, use cheaper read-only model, isolate history).
       - Mechanism pressure: "context fork" as a control mechanism; mismatch between declarative skill metadata and actual execution.
       - Confidence: medium.
       - Evidence: `research/sources/issues/src_iss_6bbe542bed6c/artifact.txt`.

    E) State persistence can introduce accidental RCE surfaces (pickle restore).
       - Finding: OpenHands allegedly uses `pickle.loads()` over FileStore state without integrity verification; risk: crafted payload -> RCE on restore; suggested fix: switch to JSON or restricted unpickler/HMAC signing.
       - Mechanism pressure: "safe state serialization" + "integrity checks" are harness mechanisms (especially for resumability).
       - Confidence: medium (issue report cites file paths; still needs source validation in codebase lane).
       - Evidence: `research/sources/issues/src_iss_f44f83f3fbc3/artifact.txt`.

    F) Tooling dependency management can block agent startup (ripgrep download hang).
       - Finding: gemini-cli startup delays due to attempted download of rg into `~/.gemini/bin/rg` hanging; system-installed rg is ignored; config `useRipgrep: false` bypasses.
       - Mechanism pressure: "dependency bootstrap policy" and "startup non-blocking initialization" matter for reliability; also "prefer system tools if present" vs "self-managed toolchain" tradeoff.
       - Confidence: low-to-medium (issue report; outside TerminalBench directly but same class of harness failure).
       - Evidence: `research/sources/issues/src_iss_677a876a6ea9/artifact.txt`.

    G) Postmortem capture failure: OpenDev architecture source is not readable as captured.
       - Finding: capture is a redirect stub + empty text; cannot extract mechanisms honestly.
       - Confidence: high (direct observation).
       - Evidence: `research/sources/postmortems/src_pmt_2c716b81f9a5/artifact.html`, `research/sources/postmortems/src_pmt_2c716b81f9a5/artifact.txt`.

    H) Low-credibility postmortem: AI-RNG "production agent" page appears ad-heavy / mixed content.
       - Finding: includes some plausible operational claims (checkpoints, safe pauses, monitors for drift), but the page content appears low signal and mixed with unrelated product/affiliate text; treat as lead only.
       - Confidence: low.
       - Evidence: `research/sources/postmortems/src_pmt_afc13590bd50/artifact.txt`.

- contradiction_or_support_notes: |
    1) Cursor "write tool outputs to files" supports the claude-code /resume crash report.
       - Informal claim: avoid truncation by writing tool outputs to files.
       - Issue pressure: storing huge tool_result blobs inline in JSONL makes resume/browsing fail.
       - Synthesis implication: file-backed artifacts + lazy reads is a concrete mechanism to reduce both context bloat and persistence fragility.
       - Evidence: `research/sources/informal/cursor_dynamic_context_discovery.md`, `research/sources/issues/src_iss_222a58240294/artifact.txt`.

    2) Cursor "chat history as files" supports "compaction is lossy" concerns, but clashes with "compaction headroom reserve" failures.
       - Cursor design assumes compaction happens and quality can be improved by history-file lookup.
       - claude-code issue suggests compaction may fail entirely when context is full (no headroom).
       - Mechanism implication: compaction needs reserved budget + possibly an emergency compaction pathway; history-file retrieval is only helpful if compaction reliably runs.
       - Evidence: `research/sources/informal/cursor_dynamic_context_discovery.md`, `research/sources/issues/src_iss_15bd3d2d6a1d/artifact.txt`.

    3) Humanlayer deterministic prefetch vs Cursor dynamic discovery: explicit tradeoff.
       - Prefetch: reduces round trips, but can waste tokens and increase contradiction/noise if overdone.
       - Dynamic discovery: reduces token bloat and contradiction pressure, but requires strong retrieval/search affordances and robust tool schema lookups.
       - Mechanism implication: harness likely needs a policy layer deciding which items are prefetched deterministically vs discovered on-demand.
       - Evidence: `research/sources/informal/humanlayer_12_factor_agents.md`, `research/sources/informal/cursor_dynamic_context_discovery.md`.

    4) Skill metadata vs execution reality: "declarative control plane" is brittle if the runtime ignores it.
       - Issue suggests skill tool ignores `context: fork` + `agent:` even when authored in SKILL.md frontmatter.
       - Implication for our harness design: if we adopt file-defined skills/rules, we need strict enforcement and clear observability when metadata is ignored.
       - Evidence: `research/sources/issues/src_iss_6bbe542bed6c/artifact.txt`, `research/sources/informal/cursor_dynamic_context_discovery.md`, `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt`.

    5) Monitoring and trace layers can be conceived as separate "agents" operating over the same interaction log.
       - Cognition pushes trace pointers for retrievability; OpenAI describes asynchronous monitor review and future synchronous blocking.
       - Mechanism implication: "secondary analysis agents" (monitors, graders) should be first-class in mechanism_map, not conflated with the executor.
       - Evidence: `research/sources/informal/cognition_agent_trace.md`, `research/sources/informal/openai_monitor_misalignment.md`.

- unvalidated_leads: |
    - AI-RNG "production agent" narrative mentions checkpoints, routing policies, verification gates, monitors for drift; treat as a hypothesis generator only until corroborated by higher-quality sources or direct code/trajectory evidence.
      Evidence: `research/sources/postmortems/src_pmt_afc13590bd50/artifact.txt`.

    - Anthropic long-running harness: claims about context resets vs compaction and 3-agent planner/generator/evaluator architecture are likely relevant to mechanism_map, but the local capture needs a cleaner read before we rely on wording/details.
      Evidence: `research/sources/informal/anthropic_long_running_harness.md`.

    - OpenAI monitoring capture contains apparently unrelated text near the end; only trust the high-level monitoring description unless validated by alternate on-disk evidence.
      Evidence: `research/sources/informal/openai_monitor_misalignment.md`.

- confidence_notes: |
    - Most items here are (a) vendor blog claims, (b) issue reports, or (c) postmortem narratives. They are valuable for mechanism pressure but must not be treated as "implemented in our target harnesses" without trajectory/source confirmation.
    - Where an issue report cites concrete file paths/sizes, it is stronger as a failure signal, but still benefits from source validation (if mirrored repos exist).
    - Treat any "performance numbers" (token reductions, etc) as provisional unless replicated in our trajectories/evals.

- open_questions: |
    - Which of these mechanisms are actually present in the in-scope terminal harness families (deepagents, terminus-kira, BigAI reconstruction) vs only present in tooling products like Cursor/Codex/claude-code?
    - Do any of the in-scope systems already implement "tool output as file" / "lazy read" patterns, and how is it reflected in trajectories?
    - How do subagents change context growth patterns in our in-scope trajectories (e.g., does any family show subagent-output summarization or headroom reservation)?
    - What is the "turn state machine" in each harness (how are interruptions, crashes, and resumes represented and reconciled)?
    - For state persistence: what formats are used (JSON, sqlite, pickle, etc), and what integrity checks exist (if any)?
    - For tool dependency management: do any harnesses block startup on downloads or tool bootstrap, and how does that affect long-horizon reliability?

- next_hand_off_target: |
    - `tracking/collab/stage_02_synthesis/mechanism_map/outputs/contradiction_analyst.md` (pressure-test: are we over-weighting tool-vendor narratives vs our corpus? did we miss a major issue cluster?)
    - Principal synthesis: use this as informal-lane input for mechanism cards around:
      - context overflow / compaction headroom
      - tool output persistence format
      - crash recovery / turn finalization
      - workspace isolation (threads/worktrees/VMs)
      - observability and monitoring layers
      - safe state serialization and integrity
