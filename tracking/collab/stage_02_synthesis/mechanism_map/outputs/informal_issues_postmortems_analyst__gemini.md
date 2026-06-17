```text
INFORMAL_ISSUES_POSTMORTEMS_OUTPUT
- artifact: mechanism_map
- role: informal/issues/postmortems analyst
- preflight_scope_confirmed: Yes, validated against corpus manifest (`corpus__captured_for_synthetic_prep.json`) and organizer matrix targets. Focus is constrained to informal blogs, issue trackers, and operator postmortems.
- preflight_planned_read_order: 1. Target triad-related issues (Terminal, Recovery, Async/Cancel, Git/Branching). 2. Key postmortems on sandbox and harness operations. 3. Broad informal signal architectures.
- preflight_critical_sources_selected: 
  - `src_iss_f07284ab370e` (Gemini CLI structured error recovery)
  - `src_iss_c684343ec3ff` (Codex Windows PTY sandbox bypass)
  - `src_iss_613424e145e5` (Claude Code state/resume bug)
  - `src_iss_b69884cd17d8` (OpenClaw auto-compaction trigger)
  - `src_iss_f44f83f3fbc3` (OpenHands state pickle deserialization)
  - `src_pmt_350e236460b0` (Cursor dynamic context & terminal as files)
  - `src_pmt_cddfa4a4dcc6` (Codex agent-first harness engineering)
  - `langchain_anatomy_of_harness.md`
  - `cursor_agent_sandboxing.md`
- preflight_coverage_risks: Informal sources and vendor postmortems (Cursor, Codex) tend to present architecture in a polished, retrospective manner. We risk adopting vendor marketing as confirmed mechanism reality unless we cross-reference with issues.
- preflight_likely_blind_spots: Closed-source platform mechanisms (like Cursor's exact sandbox runtime integration) can only be analyzed as `behavioral reconstruction` since the server-side code is unavailable.
- preflight_blockers: None.

- coverage_used:
  - `research/sources/issues/src_iss_f07284ab370e/artifact.txt`
  - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
  - `research/sources/issues/src_iss_f44f83f3fbc3/artifact.txt`
  - `research/sources/issues/src_iss_c684343ec3ff/artifact.txt`
  - `research/sources/issues/src_iss_b69884cd17d8/artifact.txt`
  - `research/sources/postmortems/src_pmt_350e236460b0/artifact.txt`
  - `research/sources/postmortems/src_pmt_afc13590bd50/artifact.txt`
  - `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt`
  - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`
  - `research/sources/informal/langchain_anatomy_of_harness.md`
  - `research/sources/informal/cursor_agent_sandboxing.md`
  - `research/sources/informal/humanlayer_ace_fca.md`
- coverage_not_yet_used:
  - Remaining informal sources in `research/sources/informal/`
  - Unrelated issues in `research/sources/issues/`
- evidence_classes_touched:
  - informal sources
  - issues
  - postmortems
- priority_sources_not_yet_read:
  - Any remaining unread trajectory-related issue threads that might detail specific async cancellation failure patterns.

- high_signal_operating_claims:
  - **Harness Encapsulation:** A model is not an agent; the "harness" provides state, tool execution, feedback loops, and enforceable constraints. Harness engineering is replacing raw prompt engineering as the primary lever for agent reliability.
  - **Dynamic Context Discovery:** Instead of injecting long terminal outputs directly into the context window, advanced harnesses (Cursor) map terminal stdout/stderr to local files. The agent uses file-search tools (`grep`, `jq`) to selectively read terminal state.
  - **Sandboxing as Core Prerequisite:** Raw bash execution is standard but highly volatile. Production agents are run within restrictive sandboxes (macOS Seatbelt, Linux seccomp/Landlock) that only prompt users when the agent attempts to step outside the sandbox (e.g., network calls).

- issue_and_postmortem_findings:
  - **Recovery/Process-Control Triad:** Agents struggle with unstructured string errors. Gemini CLI #23156 highlights that without structured `error_type`, `recoverable` flags, and `hint` fields, agents frequently retry fatally broken operations or give up on easily recoverable states.
  - **Stateful Recovery Triad:** Session state is highly fragile. Claude Code #25032 reveals that failing to update a simple `sessions-index.json` completely breaks `--resume` capability. OpenHands #13583 reveals state is often serialized unsafely (Pickle deserialization), exposing systems to RCE when restoring agent state.
  - **Terminal-Control Triad:** Codex #14367 demonstrates that PTY execution paths on Windows can bypass sandbox policies, meaning terminal abstractions often leak underlying host privileges.
  - **Context Management/Compaction:** OpenClaw #15006 shows that token cache tracking (prompt caching) is artificially inflating token counts, triggering premature auto-compaction and memory flushing loops.

- contradiction_or_support_notes:
  - **Supports Codebase Evidence:** The move toward "terminal as files" (Cursor postmortem) directly supports the `headless-terminal` triad approach where stdout/stderr are managed via file descriptors and buffers rather than direct inline string passing.
  - **Contradiction:** Vendors claim agents "reason" through errors, but issue trackers (Gemini CLI) show models frequently enter infinite loops when faced with unstructured terminal or tool errors. The operational reality requires highly structured error handling to force the model into correct recovery paths.

- unvalidated_leads:
  - Do Windows-based agent sandboxes reliably contain PTY subprocesses? (Codex #14367 implies a major architectural hole).
  - How do different harnesses handle async cancellation? The postmortems mention "interruptions" but lack concrete details on the interrupt signal propagation (SIGINT vs SIGTERM vs application-level cancellation).

- confidence_notes:
  - **High** for failure reports (Issues): These are empirical, verifiable failures in live systems.
  - **Medium** for operational/architectural claims derived from informal postmortems: These must be treated as `behavioral reconstruction` since the backend server code for systems like Cursor and Codex is proprietary.

- open_questions:
  - What is the exact schema of the "structured error" feedback loop that successfully breaks agents out of infinite retry loops?
  - How are harnesses standardizing the mapping of long-running terminal sessions to queryable files without introducing massive I/O bottlenecks?

- next_hand_off_target: `tracking/collab/stage_02_synthesis/mechanism_map/outputs/contradiction_analyst.md`
```