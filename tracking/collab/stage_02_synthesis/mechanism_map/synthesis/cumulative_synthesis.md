# Mechanism Map Cumulative Synthesis

Status: canonical cumulative state surface for `mechanism_map` as of 2026-04-10

Purpose

- This file is the canonical carry-forward control surface for `mechanism_map`.
- Update this file after each governed wave instead of treating long prose or memory as the inheritance surface.

Legacy note

- The preserved `wave_01_exploratory_anchor` still has backing detail in:
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/accepted_claims.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/contradiction_register.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/coverage_frontier.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/open_questions.md`
- Treat those files as supporting detail for Wave 01 rather than the canonical control surface.

Current artifact judgment

- `mechanism_map` now has:
  - a preserved `wave_01_exploratory_anchor`
  - Wave 02 `execution_control_and_terminal_grounding` principal synthesis with `pass_with_warnings`
  - same-wave trajectory and codebase follow-up depth
  - rerun contradiction review with `pass_with_warnings`
  - checklist adjudication accepting Wave 02 with carry-forward warnings
  - Wave 03 `verification_completion_and_recovery` first-pass lane outputs
  - three contradiction reviews:
    - primary GPT contradiction
    - Claude gate contradiction
    - Gemini gate contradiction
  - Wave 03 principal synthesis
- Wave 03 checklist adjudication accepting the wave with carry-forward warnings
- Wave 04 `context_state_memory_workspace` first-pass lane outputs
- three contradiction reviews:
  - primary GPT contradiction
  - Claude gate contradiction
  - Gemini gate contradiction
- Wave 04 principal synthesis
- Wave 04 repair-pass support-track artifacts now exist and are substantive enough for checklist
- Wave 04 checklist adjudication accepting the wave with carry-forward warnings
- Wave 05 `tools_environment_permissions` first-pass lane outputs
- three contradiction reviews:
  - primary GPT contradiction
  - Claude gate contradiction
  - Gemini gate contradiction, later superseded on the structural blocker because the missing trajectory lane now exists
- Wave 05 principal synthesis
- Wave 05 checklist adjudication accepting the wave with carry-forward warnings
- Wave 06 `planning_orchestration_and_interactions` first-pass lane outputs
- three contradiction reviews:
  - primary GPT contradiction
  - Claude gate contradiction
  - Gemini gate contradiction
- Wave 06 principal synthesis
- The three Wave 03 contradiction passes converge on `pass_with_warnings`, and checklist adjudication accepts the wave on the same basis.
- Wave 03 repair-pass support-track artifacts now exist and are substantive enough for accepted carry-forward use.
- The artifact now has stronger mechanism separation across `execution/control` and `verification/completion/recovery`.
- Wave 04 now materially strengthens mechanism separation across `context`, `state`, `memory`, and `workspace`.
- Wave 05 now materially strengthens mechanism separation across `tool gateways`, `path/cwd discipline`, `permission-policy vs capability boundaries`, and `terminal-first substrate choices`.
- Wave 06 now materially strengthens mechanism separation across `planner-first orchestration`, `delegation and role contracts`, and `anti-prestige baseline selection`.
- Wave 02 is accepted at the wave level.
- Wave 03 is accepted at the wave level with carry-forward warnings.
- Wave 04 is accepted at the wave level with carry-forward warnings.
- Wave 05 is accepted at the wave level with carry-forward warnings.
- No family is yet `decision_ready`.

Accepted claims

- Carried forward from Wave 01:
  - terminal/session control is a real, high-value harness mechanism family rather than incidental implementation noise
  - verification and external completion doctrine materially shape what counts as success
  - recovery and cleanup behavior interact strongly with execution control and state safety
- Added from Wave 02:
  - `execution_control_and_terminal_grounding` is a real cross-family mechanism domain
  - that domain should currently be split into at least three families:
    - KIRA `tmux/keystroke session control`
    - DeepAgents and similar `discrete command-and-file executors`
    - BigAI `role-separated controller` as `behavioral reconstruction`
  - newly added `autoagent` source fits the existing `discrete command-and-file executor` family rather than creating a new execution-control family
  - same-wave follow-up depth now closes the main packet-required trajectory and source gaps for Wave 02
  - completion and stopping behavior in this domain is at least three-layered:
    - in-trajectory verifier role/state
    - external grader or test-artifact layer
    - eval adapter, replay, or judge layer
  - interruptibility, cleanup, and repeated state checks are load-bearing execution-control mechanisms, not incidental details

Added from Wave 03

- `verification_completion_and_recovery` should currently be split into multiple mechanism families rather than treated as one stable family:
  - artifact-backed postcondition proof
  - layered verifier / grader / replay separation
  - cleanup and delivery hygiene as part of completion
  - checkpoint / resume substrate as an exploratory candidate only
- DeepAgents `db-wal-recovery` currently supports a narrower claim than the first-pass rhetoric implied:
  - the visible proof path is inline agent-authored verification in the trajectory
  - not yet a clearly mirrored framework verifier path
- KIRA carries two distinct truths at once:
  - source-visible completion gating is real
  - perception-heavy false-completion pressure is also real in the `extract-moves-from-video` slice
- A-Evolve is currently the clearest source-visible family for separating:
  - agent completion signal
  - external verification
  - rollback/versioning recovery
- BigAI continues to support a strong verifier-mediated family only as `behavioral reconstruction`
- Restart and restart-safe resumability remain under-evidenced behaviorally and should not yet be promoted beyond `exploratory`

Added from Wave 04

- The strongest current Wave 04 baseline is `explicit artifact continuity and workspace state`, not demonstrated durable long-term memory retrieval.
- `context compaction`, `session history`, `durable persistence`, and `workspace artifacts` should currently be treated as distinct mechanism surfaces rather than one memory family.
- `workspace and branch hygiene` is real as a state-safety family, but current strong evidence is regime-scoped to `git-multibranch` plus path/session corruption pressure rather than universal.
- `custom-memory-heap-crash` should not be read as evidence about coding-agent long-term memory; it is primarily a runtime allocator and cleanup state surface.
- A-Evolve is currently the clearest source-backed workspace-artifact family, but this remains source-backed rather than trajectory-backed in Wave 04.
- BigAI remains the most elaborate visible handoff and cleanup family in the required trajectories only as `behavioral reconstruction`.
- Durable long-term retrieval memory remains `exploratory` in `mechanism_map` because the required Wave 04 trajectories do not visibly exercise it as the dominant state carrier.

Added from Wave 05

- `tools_environment_permissions` is a real cross-family mechanism domain rather than a thin appendix to execution control.
- Tool gateway design should currently be treated as a real family-separation surface:
  - DeepAgents `execute` plus file tools
  - KIRA `bash_command` plus optional `image_read`
  - BigAI `run/wait/kill/interact` shell-job control as `behavioral reconstruction`
  - A-Evolve minimal terminal baseline plus broader MCP expansion as source-backed pressure
- `cwd/workdir/path discipline` is a real mechanism family and should not be hidden inside generic debugging or environment setup.
- `permission policy` and `execution capability boundaries` should currently be treated as distinct mechanism layers.
- Permission failure pressure already separates into at least two families:
  - under-enforcement or policy bypass
  - over-prompting or approval-burst collapse
- The strongest direct Wave 05 baseline remains `terminal-first minimal tooling`, not browser-first or prestige tool expansion.
- `environment discovery` remains `exploratory` as a stable cross-family mechanism because direct trajectory evidence is still uneven.

Added from Wave 06

- `planning_orchestration_and_interactions` is a real cross-family mechanism domain rather than generic workflow rhetoric.
- `planner-first orchestration with conditional verifier gate` is real in the required BigAI slices, but should stay scoped as `behavioral reconstruction` rather than cross-family universal truth.
- `delegation and role-boundary governance` are source-backed in deepagents, KIRA, and a-evolve, but source-visible orchestration capacity still exceeds required-task trajectory exercise for deepagents and a-evolve.
- `terminal-first single-agent baseline versus prestige orchestration` is now a first-class mechanism judgment, not just a preference note.
- `interaction contract fragility` is real and load-bearing:
  - delegation mismatch
  - coordination stall
  - context-boundary conflicts
  - permission-hook bypass
- verifier optionality is real as a visible regime distinction, but its causal policy is still unresolved.

Contradiction register

- Wave 01 carry-forward tension:
  - source intent versus observed behavior still needed more direct reconciliation
- Wave 02 strengthened tensions:
  - KIRA and DeepAgents both satisfy `execution control`, but not via the same visible implementation substrate
  - internal verifier `PASSED` and final graded success can diverge within the same run
  - BigAI remains useful only as documentation-plus-trajectory reconstruction, not source-backed implementation
  - repo-state-safe branching and cleanup is still thinner than terminal and cancellation claims
  - organizer-based coverage rhetoric should not outrank concrete path accounting
- Wave 03 active tensions:
  - trajectory-visible DeepAgents completion proof is stronger than its currently traced framework-source attribution
  - formal literature is verifier-heavy while direct evidence still supports minimal-sufficient artifact-backed proof
  - cleanup confirmation is stronger in direct evidence than in the current formal slice
  - restart/resume substrate is stronger in source and docs than in direct behavioral proof
  - KiraClaw session-state and replay surfaces are more substantial than the main codebase lane first emphasized
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` remains empty, so organizer routing is still not a trustworthy coverage-control surface
- Wave 04 active tensions:
  - source-visible durable memory capacity is richer than the required trajectory window exercises in DeepAgents and KIRA
  - BigAI docs and reconstruction imply a memory layer, but direct implementation remains hidden
  - A-Evolve is the clearest source-backed workspace family, but lacks Wave 04 trajectory reconciliation
  - branch/workspace hygiene is strong in `git-multibranch` and weaker outside that regime
  - compaction and resume substrate are strong in formal and informal evidence, but direct Wave 04 trajectories do not fully exercise them
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` remains empty, so organizer routing is still not a trustworthy coverage-control surface
- Wave 05 active tensions:
  - source-visible permission and approval machinery is richer than the required trajectories visibly exercise
  - informal issue pressure shows strong policy-runtime mismatch and prompt storms that the required trajectories only partially expose
  - A-Evolve materially strengthens the Wave 05 source picture but lacks required-trajectory reconciliation in this packet
  - browser/tool reliability pressure is currently stronger in issue evidence than in required direct trajectories
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md` is still missing, so support-track closure is imperfect
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` remains empty, so organizer routing is still not a trustworthy coverage-control surface
- Wave 06 active tensions:
  - explicit planner/executor/verifier role separation is strongest in BigAI behavioral evidence, while sampled deepagents and KIRA required-task trajectories remain closer to single-agent loops
  - deepagents and a-evolve source-visible delegation capacity exceeds required-slice trajectory exercise
  - planner completion and verifier acceptance are visibly split, but the coupling rule between them is not causally explained
  - role-handoff fragility is real, but direct cross-family behavioral saturation is still partial
  - BigAI remains source-opaque, so scheduler heuristics and verifier optionality rules remain unresolved
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` remains empty, so organizer routing is still not a trustworthy coverage-control surface

Coverage frontier

- The most important active gaps are:
  - deeper trajectory pressure on archive-only and long-tail variants in:
    - `git-multibranch`
    - `db-wal-recovery`
    - `break-filter-js-from-html`
    - `headless-terminal`
    - `large-scale-text-editing`
  - deeper source excavation in:
    - `research/sources/codebases/quarantine/claw-code/**`
    - `research/sources/codebases/src_cod_*/**`
    - KIRA Harbor session internals behind `TmuxSession`
    - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/memory_manager/**`
    - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/memory_retriever/**`
  - narrower but still real formal-source gaps where unread papers could materially change the execution-control judgment
  - narrower eval-side raw-bundle pressure on the same execution-control domain
  - archive pressure families from `src_cod_*` are now useful exploratory inputs, but they are not yet in-wave trajectory-reconciled Wave 02 core families
  - direct BigAI verifier-heavy trajectory pressure remains thin without `adaptive-rejection-sampler`
  - organizer-driven routing remains unavailable because `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` is still empty
  - Wave 05 still needs:
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`
    - optional `git-multibranch` long-tail pressure for cwd/workdir and workspace-boundary robustness
    - deeper browser-reliability trajectory pressure beyond issue clusters
    - stronger trajectory-side approval-policy evidence
    - A-Evolve trajectory reconciliation in the tools/environment domain
    - stronger local-harness implementation depth beyond current `blocks/` and `runner/` stubs
  - Wave 06 still needs:
    - direct expansion of `research/sources/trajectories/BigAI/prove-plus-comm/cd0d69dd-3cac-47e0-9777-51327561ff6d.tar.gz`
    - deeper deepagents delegation-heavy trajectory pressure
    - deeper a-evolve Wave 06-family trajectory pressure
    - HITL delegation and interruption contract analysis
    - deeper postmortem durability checks for orchestration failure closure

Open questions

- Does deeper `src_cod_*` reading add another source-backed PTY family, or does it reinforce the discrete-command family?
- How much of KIRA's low-level session behavior changes once Harbor `TmuxSession` internals are read directly?
- Is BigAI's terminal substrate truly PTY-backed, mixed, or command-executor-plus-role-layering?
- How robust is repo-state-safe cleanup once raw `git-multibranch`, `db-wal-recovery`, and `break-filter-js-from-html` archives are pressure-tested more deeply?
- In DeepAgents `db-wal-recovery`, should the inline verification script be treated as:
  - agent-authored proof riding the execution substrate
  - task-fixture logic
  - or hidden harness injection not yet traced?
- Which exact conditions cause BigAI verifier `PASSED` to diverge from overall run failure?
- Are cleanup and delivery hygiene benchmark-enforced in the relevant families, or mainly family-local doctrine?
- What direct trajectory evidence would be enough to promote restart-safe resumability beyond `exploratory`?
- Which trajectories, if any, visibly exercise durable memory retrieval rather than artifact continuity, script replay, or checklist/todo state?
- How much does the broader KIRA memory family change once KIRA-Slack memory-manager and retriever paths are read?
- Is A-Evolve's workspace-artifact doctrine behaviorally dominant in real trajectories, or only source-visible in the current corpus slice?
- How much of current workspace hygiene confidence survives outside `git-multibranch`?
- Which local harness block should own the cwd/path contract so it stays swappable and composable with multiple execution blocks?
- What is the minimal approval-policy layer that proves policy-to-runtime equivalence without creating approval storms?
- Which tasks truly justify leaving the terminal-first minimal tooling baseline?
- How much of browser reliability can be promoted from issue pressure to direct trajectory-backed mechanism evidence?
- What exact trajectory evidence would be enough to promote environment discovery beyond `exploratory`?
- What controller rule makes verifier optional in some BigAI runs but dominant in others?
- Which deepagents and a-evolve trajectory slices most honestly pressure-test delegation-heavy orchestration against the simpler baseline?
- What is the minimum information-gain threshold that justifies moving from terminal-first single-agent loops to richer role-separated orchestration in the local harness?
- Which explicit handoff payload rules best prevent context poisoning and coordination drift?

Saturation status

- Wave 01 remains `exploratory` and `emerging` only.
- Wave 02 promotions:
  - KIRA `tmux/keystroke session control`: `emerging`
  - discrete command-and-file execution family: `emerging`
  - layered completion doctrine: `emerging`
  - BigAI role-separated controller: `exploratory`
  - repo-state-safe cleanup and branch hygiene: `exploratory`
- Wave 03 promotions:
  - artifact-backed postcondition proof: `emerging`
  - layered verifier / grader / replay separation: `emerging`
  - cleanup-confirmed completion: `emerging`
  - checkpoint / resume substrate: `exploratory`
- Wave 04 provisional promotions:
  - explicit artifact continuity and workspace state: `emerging`
  - layered context / compaction / persistence / workspace substrates: `emerging`
  - workspace and branch hygiene regime: `emerging`
  - durable long-term retrieval memory as dominant state carrier: `exploratory`
- Wave 05 provisional promotions:
  - tool gateway family separation: `emerging`
  - cwd/workdir/path contract: `emerging`
  - layered permission policy vs capability boundary: `emerging`
  - terminal-first minimal tooling baseline: `emerging`
  - process lifecycle and cancellation boundary control: `emerging`
  - environment discovery as stable cross-family mechanism: `exploratory`
- Wave 06 provisional promotions:
  - planner-first orchestration with conditional verifier gate: `emerging`
  - source-backed delegation and role-boundary governance: `emerging`
  - anti-prestige terminal-first baseline selection: `emerging`
  - interaction contract fragility as a stable failure-bearing surface: `emerging`
- No current mechanism family should be treated as `decision_ready`.

Adjudication warnings still carried forward

- Do not treat Wave 02 as `decision_ready`.
- Do not treat missing formal-paper depth as proof that formal pressure is already adequate.
- Do not flatten KIRA, DeepAgents, and BigAI into one universal terminal-control family.
- Do not treat repo-state-safe cleanup as equally resolved with terminal control and cancellation.
- Do not promote archive-only `src_cod_*` pressure families into core Wave 02 families without in-wave trajectory reconciliation.
- Do not treat restart/resumability as positively established from Wave 03.
- Do not treat DeepAgents inline proof in `db-wal-recovery` as mirrored framework verifier code until traced more directly.
- Do not treat BigAI beyond `behavioral reconstruction`.
- Do not treat the empty organizer control surface as evidence that organizer-based coverage routing is ready.
- Do not treat A-Evolve source-backed workspace state as Wave 04 trajectory-backed behavior.
- Do not treat rich source-visible memory capacity in DeepAgents or KIRA as proof that the required Wave 04 trajectories exercised durable retrieval.
- Do not flatten runtime allocator-memory failures into agent memory mechanisms.
- Do not promote robust permission safety from Wave 05; trajectory evidence is still thinner than source, formal, and issue pressure.
- Do not promote environment discovery beyond `exploratory`.
- Do not treat A-Evolve Wave 05 findings as trajectory-reconciled.
- Do not treat browser/tool prestige as stronger than the current terminal-first baseline.

Next governed step

- Treat Wave 02 as accepted history with carry-forward warnings.
- Keep its warnings explicit in later mechanism work.
- Treat Wave 03 as accepted history with carry-forward warnings.
- Keep Wave 03 warnings explicit in later mechanism work.
- Treat Wave 04 as accepted history with carry-forward warnings.
- Keep Wave 04 warnings explicit in later mechanism work.
- Treat Wave 05 as accepted history with carry-forward warnings.
- Keep Wave 05 warnings explicit in later mechanism work.
- Open Wave 06 `planning_orchestration_and_interactions`.
