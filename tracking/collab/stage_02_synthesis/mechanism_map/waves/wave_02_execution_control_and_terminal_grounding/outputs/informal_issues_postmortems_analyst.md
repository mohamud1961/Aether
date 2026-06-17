INFORMAL_ISSUES_POSTMORTEMS_OUTPUT
- artifact: `mechanism_map`
- role: `informal/issues/postmortems analyst`
- preflight_scope_confirmed:
  - observation: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/brief.md` explicitly defines this packet as a vertical mechanism-domain wave for `execution_control_and_terminal_grounding`, not a source-only or trajectory-only pass.
  - observation: The same brief states that trajectories are the primary empirical anchor for this wave, and `tracking/collab/stage_02_synthesis/tracing_readiness/outputs/tracing_readiness.md` confirms readable direct trajectory text for `headless-terminal` and `cancel-async-tasks` across `BigAI`, `deepagents`, and `terminus-kira`, plus readable `git-multibranch` coverage in `terminus-kira`.
  - observation: `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json` includes the issue and postmortem source IDs used in this pass.
  - inference: There is enough behavior visibility to use informal/issues/postmortems as contradiction pressure rather than as the empirical anchor.
- preflight_planned_read_order:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/brief.md`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - sampled trajectory anchors for PTY control, cancellation, and repo-state work
  - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
  - high-signal informal and postmortem writeups on sandboxing, context management, long-running harnesses, worktrees, and cloud execution
  - issue captures on approvals, sandbox bypasses, compaction, resume, corruption, and checkpoint/restore pressure
- preflight_critical_sources_selected:
  - trajectory anchors:
    - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
    - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
    - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
    - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
    - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
    - `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
  - source-pressure routing aid:
    - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
  - informal and postmortem pressure:
    - `research/sources/informal/cursor_dynamic_context_discovery.md`
    - `research/sources/informal/cursor_agent_sandboxing.md`
    - `research/sources/informal/cursor_agent_computer_use.md`
    - `research/sources/informal/humanlayer_ace_fca.md`
    - `research/sources/informal/anthropic_long_running_harness.md`
    - `research/sources/postmortems/src_pmt_350e236460b0/artifact.txt`
    - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`
    - `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt`
    - `research/sources/postmortems/src_pmt_afc13590bd50/artifact.txt`
  - issue pressure:
    - `research/sources/issues/src_iss_c684343ec3ff/artifact.txt`
    - `research/sources/issues/src_iss_8ceca39ae528/artifact.txt`
    - `research/sources/issues/src_iss_594e5f13600f/artifact.txt`
    - `research/sources/issues/src_iss_f736e544a5b9/artifact.txt`
    - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
    - `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt`
    - `research/sources/issues/src_iss_836cb2fc3bdb/artifact.txt`
    - `research/sources/issues/src_iss_da41417f5655/artifact.txt`
    - `research/sources/issues/src_iss_31cf9134cefa/artifact.txt`
    - `research/sources/issues/src_iss_e88081f909bc/artifact.txt`
    - `research/sources/issues/src_iss_b5d3d874490a/artifact.txt`
    - `research/sources/issues/src_iss_98321aba9fd0/artifact.txt`
    - `research/sources/issues/src_iss_5d861db09829/artifact.txt`
  - minimal-sufficient contender kept visible:
    - file-backed compaction/reset and shell-native iteration, as described in `research/sources/informal/humanlayer_ace_fca.md` and reinforced by `research/sources/informal/cursor_dynamic_context_discovery.md`, should remain visible against more elaborate planner/generator/evaluator architectures.
- preflight_coverage_risks:
  - observation: `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` was empty on read, so routing had to rely on the wave brief, manifest, tracing-readiness output, and direct source inspection.
  - observation: The issue corpus sampled here is skewed toward Codex and Claude surfaces, especially Windows and macOS failure reports.
  - observation: Several high-signal informal/postmortem documents are vendor-authored self-reports.
  - inference: This pass is strong for contradiction pressure and operator desiderata, but weaker for estimating prevalence across the full harness family space.
- preflight_likely_blind_spots:
  - unread `db-wal-recovery` trajectory slices may strengthen or weaken the checkpoint/resume story
  - same-wave source reconciliation for KIRA and DeepAgents is not performed in this role
  - verifier/benchmark implications were not opened beyond brief incidental mentions in the informal lane
  - BigAI remains partly `behavioral reconstruction`
- preflight_blockers: `[]`
- coverage_used:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/brief.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/brief.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_01_exploratory_anchor/synthesis/principal_synthesis.md`
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`
  - `tracking/collab/stage_02_synthesis/coverage_access/decision.md`
  - `tracking/collab/stage_02_synthesis/tracing_readiness/outputs/tracing_readiness.md`
  - `prompts/deep_synthesis_informal_issues_postmortems_analyst_prompt.md`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
  - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
  - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
  - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
  - `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
  - `research/sources/informal/cursor_dynamic_context_discovery.md`
  - `research/sources/informal/cursor_agent_sandboxing.md`
  - `research/sources/informal/cursor_agent_computer_use.md`
  - `research/sources/informal/humanlayer_ace_fca.md`
  - `research/sources/informal/anthropic_long_running_harness.md`
  - `research/sources/issues/src_iss_c684343ec3ff/artifact.txt`
  - `research/sources/issues/src_iss_8ceca39ae528/artifact.txt`
  - `research/sources/issues/src_iss_594e5f13600f/artifact.txt`
  - `research/sources/issues/src_iss_f736e544a5b9/artifact.txt`
  - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
  - `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt`
  - `research/sources/issues/src_iss_836cb2fc3bdb/artifact.txt`
  - `research/sources/issues/src_iss_da41417f5655/artifact.txt`
  - `research/sources/issues/src_iss_31cf9134cefa/artifact.txt`
  - `research/sources/issues/src_iss_e88081f909bc/artifact.txt`
  - `research/sources/issues/src_iss_b5d3d874490a/artifact.txt`
  - `research/sources/issues/src_iss_98321aba9fd0/artifact.txt`
  - `research/sources/issues/src_iss_5d861db09829/artifact.txt`
  - `research/sources/postmortems/src_pmt_350e236460b0/artifact.txt`
  - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`
  - `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt`
  - `research/sources/postmortems/src_pmt_afc13590bd50/artifact.txt`
- coverage_not_yet_used:
  - `research/sources/trajectories/*/db-wal-recovery/*-traj.txt`
  - `research/sources/informal/cursor_long_running_agents.md`
  - `research/sources/informal/cursor_self_driving_codebases.md`
  - `research/sources/informal/cursor_self_summarization.md`
  - `research/sources/informal/cognition_closing_agent_loop.md`
  - `research/sources/informal/cognition_agent_trace.md`
  - `research/sources/issues/src_iss_51e11ab8bc0e/artifact.txt`
  - `research/sources/issues/src_iss_72d11ef0f608/artifact.txt`
  - `research/sources/issues/src_iss_84bccb83da69/artifact.txt`
  - `research/sources/postmortems/src_pmt_2c716b81f9a5/artifact.txt`
  - `research/sources/postmortems/src_pmt_ca79e818d699/artifact.txt`
- evidence_classes_touched:
  - `trajectories`
  - `informal sources`
  - `issues`
  - `postmortems`
  - `relevant local analysis`
- priority_sources_not_yet_read:
  - `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
  - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  - `research/sources/informal/cursor_long_running_agents.md`
  - `research/sources/informal/cursor_self_driving_codebases.md`
  - `research/sources/informal/cursor_self_summarization.md`
  - `research/sources/issues/src_iss_51e11ab8bc0e/artifact.txt`
  - `research/sources/issues/src_iss_72d11ef0f608/artifact.txt`
  - `research/sources/issues/src_iss_84bccb83da69/artifact.txt`
- high_signal_operating_claims:
  - claim: Externalized artifacts are treated as the practical grounding substrate for long-running terminal work.
    observation: `research/sources/informal/cursor_dynamic_context_discovery.md` says Cursor writes long tool outputs and integrated terminal sessions to files so the agent can `tail`, `grep`, and recover specifics later. `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt` says OpenAI made docs, plans, logs, metrics, traces, and worktree-local app instances legible in-repo. `research/sources/informal/humanlayer_ace_fca.md` advocates intentional compaction into structured artifacts, and `research/sources/informal/anthropic_long_running_harness.md` describes structured handoff artifacts between fresh sessions.
    inference: Across distinct operator accounts, execution control is being stabilized by moving state out of chat memory and into inspectable files, plans, traces, and handoff artifacts.
    confidence: `medium`
    weakening_factors: Mostly self-reported vendor/operator prose; trajectory sampling here only lightly checks support.
  - claim: Long-horizon control is being pushed from compaction-only toward resets, resumability, and explicit orchestration.
    observation: `research/sources/informal/anthropic_long_running_harness.md` explicitly argues that compaction preserved continuity but did not provide a clean slate, and that context resets plus handoff artifacts became essential. `research/sources/informal/humanlayer_ace_fca.md` says workflows should be designed around frequent intentional compaction, while `research/sources/issues/src_iss_31cf9134cefa/artifact.txt` and `research/sources/issues/src_iss_e88081f909bc/artifact.txt` request or roadmap durable tasks, checkpoints, pause/resume, and restore flows.
    inference: The informal lane sees long-running control as an orchestration and lifecycle problem, not just a better prompt problem.
    confidence: `medium`
    weakening_factors: Some evidence is feature pressure or roadmap language rather than validated deployed behavior.
  - claim: Verification artifacts are becoming part of the runtime control loop rather than a post-hoc reporting layer.
    observation: `research/sources/informal/cursor_agent_computer_use.md` says cloud agents validate work with videos, screenshots, and logs. `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt` says Codex reproduces bugs, validates fixes by driving the app, records failure and success videos, and uses logs/metrics/traces as task-legible surfaces. `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt` says Automations land in a review queue and that elevated actions still require permission.
    inference: Completion claims increasingly depend on environment-facing evidence artifacts, not merely on tool-call success.
    confidence: `medium`
    weakening_factors: Strongest evidence is product-team writeups; cross-family field validation is still partial.
  - claim: Safe parallelism is operationalized through isolation boundaries such as worktrees and VMs.
    observation: `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt` says the Codex app gives each agent an isolated code copy with worktree support. `research/sources/informal/cursor_agent_computer_use.md` says Cursor cloud agents run inside isolated VMs. `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt` says OpenAI made the app bootable per git worktree and provisioned ephemeral observability per worktree.
    inference: Repo-state-safe execution is being treated as an isolation problem first, with coordination layered on top.
    confidence: `medium`
    weakening_factors: This lane shows strong operator intent but not yet enough negative evidence about failure rates across systems.
  - claim: Sandbox usability is viewed as a harness-rendering problem, not just an OS policy problem.
    observation: `research/sources/informal/cursor_agent_sandboxing.md` says Cursor had to change shell tool descriptions and failure rendering because agents were retrying commands without adjusting permissions; once sandbox constraints and escalation hints were surfaced explicitly, recovery improved.
    inference: Permission semantics must be legible inside the control loop; otherwise the agent keeps acting as though the terminal surface is opaque or nondeterministic.
    confidence: `medium`
    weakening_factors: Single-vendor writeup; issue corpus below shows that legibility is still brittle in practice.
- issue_and_postmortem_findings:
  - finding: Sandbox and approval paths are both over-blocking and under-enforcing, especially on Windows.
    observation: `research/sources/issues/src_iss_8ceca39ae528/artifact.txt` reports approval prompts for almost every command, including `find`, `sed`, and `ls`. `research/sources/issues/src_iss_594e5f13600f/artifact.txt` reports `default.rules` allow decisions still not suppressing sandbox-escape approvals. `research/sources/issues/src_iss_c684343ec3ff/artifact.txt` reports a Windows unified-exec PTY path running outside the intended sandbox with network access still reachable.
    inference: Safe action execution cannot be assumed to be a solved substrate; permission handling itself is an active failure mode that can either stall runs or silently defeat policy.
    confidence: `high`
    weakening_factors: Strong on existence, weaker on prevalence outside reported platforms.
  - finding: Resume, compaction, and session-state persistence remain fragile enough to undercut long-running control claims.
    observation: `research/sources/issues/src_iss_f736e544a5b9/artifact.txt` reports compaction hanging indefinitely and ignoring `Ctrl+C`. `research/sources/issues/src_iss_613424e145e5/artifact.txt` reports stale or missing session indexes for resume. `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt` reports silent resume failure after API-error endings. `research/sources/issues/src_iss_836cb2fc3bdb/artifact.txt` reports `.claude.json` corruption due to concurrent read/write conflicts under Remote Control.
    inference: The corpus shows strong demand for resumable long-running work, but user-facing resume/compaction layers are still brittle enough to be a core contradiction source.
    confidence: `high`
    weakening_factors: Most incidents come from one harness family, so cross-family generality is not fully established.
  - finding: Durable task execution, checkpoints, and restore surfaces are still under active construction.
    observation: `research/sources/issues/src_iss_31cf9134cefa/artifact.txt` requests durable execution with crash recovery, pause/resume, retries, journaling, and cancel safety. `research/sources/issues/src_iss_e88081f909bc/artifact.txt` says Gemini CLI is moving spec workflow versioning onto checkpointing in a shadow git repo and `/restore`. `research/sources/issues/src_iss_b5d3d874490a/artifact.txt` says restore flows still lack direct unit coverage.
    inference: Checkpoint/restore has become a visible control-surface family, but this lane currently shows roadmap pressure and test-gap evidence more than mature, reconciled behavior.
    confidence: `medium`
    weakening_factors: This is partly aspirational and partly internal-roadmap evidence.
  - finding: False completion without target-side verification is a real operational hazard.
    observation: `research/sources/issues/src_iss_5d861db09829/artifact.txt` reports repeated `[completed]` status claims after host-side copy operations without verifying that the target device actually booted or ran the deployed code.
    inference: In stateful or external-device tasks, command success is not a safe stop rule unless the harness separately validates target-side effects.
    confidence: `low`
    weakening_factors: Single-user report with no corroborating trajectory in this pass, but severity is high enough that the failure mode should remain visible.
  - finding: Long-running browser or external-environment tasks still lack robust autonomous recovery.
    observation: `research/sources/issues/src_iss_da41417f5655/artifact.txt` reports an OpenHands agent getting stuck after browser crash because no health check or watchdog exists.
    inference: Interactive-environment control is still brittle once the environment stops responding; watchdogs and state resumption remain a recurring gap.
    confidence: `medium`
    weakening_factors: Single issue report; no corroborating OpenHands trajectory in this wave.
- contradiction_or_support_notes:
  - note: Informal claims that terminal control is a real mechanism family are supported by sampled trajectory behavior.
    observation: `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt` shows explicit PTY-backed interactive bash and direct tests for `.bashrc`, interactive REPL behavior, and `Ctrl-C`. `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt` shows repeated requirement checklists and verification before `task_complete`. `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt` and `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md` show planner/executor/verifier structure around the same family.
    inference: The informal lane is not inventing terminal grounding out of whole cloth; it is reinforcing a behavior-visible family already present in trajectories.
    confidence: `high`
  - note: Informal pressure for cancellation-safe cleanup is supported by direct cancellation trajectories.
    observation: `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt` explicitly tests cancellation cleanup and awaits cancelled tasks so `finally` blocks run. `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt` builds a worker-queue design and tests cancellation, exception propagation, and cleanup. `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt` shows the same topic under planner/executor/verifier control.
    inference: Cleanup-on-interrupt is behaviorally real in the sampled corpus, so issue pressure for stronger resume/checkpointing should be read as pressure on the next layer above basic cancellation safety.
    confidence: `high`
  - note: Sandbox marketing claims are under direct contradiction pressure from issue evidence.
    observation: `research/sources/informal/cursor_agent_sandboxing.md` says sandboxing reduces interruptions and agents recover better once failures render the right constraint. `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt` says project/team rules can authorize elevated commands. Against that, `research/sources/issues/src_iss_8ceca39ae528/artifact.txt`, `research/sources/issues/src_iss_594e5f13600f/artifact.txt`, and `research/sources/issues/src_iss_c684343ec3ff/artifact.txt` show prompt spam, rule mismatch, and outright PTY sandbox bypass.
    inference: The governance surface is not just "sandbox yes/no"; the exact execution path and rule-shape rendering materially determine whether the system is safe, usable, or both.
    confidence: `high`
  - note: Long-running-harness writeups endorse resets, handoffs, and durable state, but issue evidence says those very layers are still fragile.
    observation: `research/sources/informal/anthropic_long_running_harness.md` says resets plus structured handoffs became essential. `research/sources/informal/humanlayer_ace_fca.md` recommends frequent intentional compaction. Yet `research/sources/issues/src_iss_f736e544a5b9/artifact.txt`, `research/sources/issues/src_iss_613424e145e5/artifact.txt`, and `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt` show compaction hangs, stale resume indexes, and silent resume failure.
    inference: The corpus currently supports the mechanism family at the design level but not dependable field reliability for its user-facing implementations.
    confidence: `high`
  - note: Isolation claims for worktrees and VMs do not automatically solve shared control-state corruption.
    observation: `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt`, `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`, and `research/sources/informal/cursor_agent_computer_use.md` all emphasize isolated copies or VMs. `research/sources/issues/src_iss_836cb2fc3bdb/artifact.txt` shows concurrent writer corruption of `.claude.json`.
    inference: Code checkout isolation and session/control-plane isolation are separate mechanism layers; the first can be strong while the second remains brittle.
    confidence: `medium`
    weakening_factors: Shared-state corruption evidence is from one harness family and one platform.
- unvalidated_leads:
  - `research/sources/postmortems/src_pmt_afc13590bd50/artifact.txt` uses vocabulary that matches checkpoints, approvals, budgets, and run reports, but the artifact appears partly synthetic/contaminated and should be treated as low-confidence desiderata rather than evidence-backed field behavior.
  - `research/sources/issues/src_iss_98321aba9fd0/artifact.txt` suggests a possible mechanism family of executable preflight/startup hooks rather than context-only startup instructions. This is relevant to control-loop grounding, but it remains a feature request plus reproduced conversation, not a settled mechanism.
  - `research/sources/issues/src_iss_949d7288362a/artifact.txt` showed capture mismatch on read relative to its title and should be revalidated before use.
  - `research/sources/issues/src_iss_e88081f909bc/artifact.txt` and `research/sources/issues/src_iss_b5d3d874490a/artifact.txt` may matter more if later wave passes find restore/checkpoint behavior directly in trajectories or source.
- confidence_notes:
  - Strongest confidence is on contradiction existence where multiple issue captures and sampled trajectories agree that execution control, cancellation cleanup, and verification gates are real surfaces.
  - Confidence is lower when evidence comes primarily from vendor-authored postmortems, from single-user issue reports, or from roadmap/feature-request language.
  - This role did not read same-wave source-system artifacts deeply enough to arbitrate source intent versus issue reports; that remains for cross-role synthesis.
- open_questions:
  - Which harness families in the corpus have durable resume/checkpoint behavior that is visible in trajectories or source, rather than only in blogs, issues, or roadmap items?
  - How much of the sandbox/approval contradiction is Windows-specific execution-path drift versus a broader harness design problem?
  - Do `db-wal-recovery` and other stateful slices show stronger repo-state-safe cleanup and restore behavior than the current terminal/cancellation slices?
  - Are executable startup/preflight hooks emerging as a distinct control mechanism family, or are they a patch for weak instruction-following?
  - How much isolation is actually needed for repo-state safety once shared session metadata, auth state, and remote-control surfaces are accounted for?
- next_hand_off_target: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/contradiction_analyst.md`
