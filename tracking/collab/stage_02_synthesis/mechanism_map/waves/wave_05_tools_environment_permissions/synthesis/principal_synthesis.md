# Mechanism Map Wave 05 Principal Synthesis

Status date: 2026-04-09

Wave

- `wave_05_tools_environment_permissions`

Overall judgment

- Wave 05 materially strengthens `mechanism_map`.
- The strongest supported Wave 05 conclusion is that `tools`, `environment handling`, and `permission boundaries` should not be collapsed into generic execution-control rhetoric.
- The wave supports multiple real mechanism families inside this domain.
- The contradiction surface now supports `pass_with_warnings`.
  - The earlier `blocked` Gemini contradiction was structural and is now superseded because the missing trajectory lane was later produced and reconciled (`tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/contradiction_analyst__gemini.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/contradiction_analyst__claude.md`).
- BigAI remains `behavioral reconstruction`.
- The wave does not support a strong positive claim that approval policy is already trajectory-proven as robust across families.
- The wave is now principal-complete and checklist-ready.
- Wave 05 is not yet accepted at the wave level, is not artifact completion, and no family is `decision_ready`.

What this wave resolved

- `tool gateway shape` is a real cross-family mechanism axis rather than incidental interface variance.
  - DeepAgents shows a compact `execute` plus file-tool loop (`research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`, `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/filesystem.py`).
  - Terminus-KIRA shows terminal-first `bash_command` control with optional `image_read` rather than a browser- or MCP-first substrate (`research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`, `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`).
  - BigAI shows a distinct `run/wait/kill/interact` shell-job family, but only as `behavioral reconstruction` (`research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`, `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`).
  - A-Evolve source adds a two-tier picture: a minimal deterministic terminal baseline plus broader MCP expansion (`research/sources/codebases/a-evolve/seed_workspaces/terminal/tools/registry.yaml`, `research/sources/codebases/a-evolve/agent_evolve/agents/mcp/agent.py`).
- `cwd/workdir/path discipline` is a first-order mechanism family, not just debugging detail.
  - BigAI `cancel-async-tasks` shows a hard correctness boundary when `/tmp` pathing fails and `/app` pathing succeeds (`research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`).
  - DeepAgents source encodes explicit path validation and an absolute-path doctrine (`research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/utils.py`, `research/sources/codebases/deepagents/libs/cli/deepagents_cli/agent.py`).
  - KIRA process management resolves and validates cwd under workspace control (`research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_manager.py`).
  - Informal issue evidence independently strengthens path-shape and wrong-target edit risk as a real operational cluster (`tracking/collab/stage_02_synthesis/informal_cluster_dossiers/tools_environment_permissions.md`).
- `permission policy` and `execution capability boundaries` are separate surfaces and should stay separate.
  - DeepAgents distinguishes runtime execution capability from HITL or allow-list policy (`research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/local_shell.py`, `research/sources/codebases/deepagents/libs/cli/deepagents_cli/agent.py`).
  - KIRA shows explicit allow/deny/ask policy in KiraClaw while other KIRA-family paths still expose `bypassPermissions`, which means family-wide doctrine is heterogeneous rather than uniform (`research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/engine.py`, `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/bot_call_detector/agent.py`).
  - Formal sources independently separate authorization doctrine from sandbox containment and path/root constraints (`tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md`).
- `permission handling` is not one pass/fail surface; it is already split into at least two failure modes.
  - Informal evidence converges on under-enforcement and over-prompting as distinct failure clusters (`tracking/collab/stage_02_synthesis/informal_cluster_dossiers/tools_environment_permissions.md`).
  - This sharpens the wave-level synthesis: permission design must cover both policy-to-runtime integrity and approval-volume usability.
- `terminal-first minimal tooling` remains the strongest direct baseline in the required Wave 05 slices.
  - The required trajectories do not support browser-first superiority.
  - KIRA's `image_read` is a conditional uplift, not substrate replacement (`research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`).
  - Informal evidence adds browser reliability pressure rather than browser superiority proof (`tracking/collab/stage_02_synthesis/informal_cluster_dossiers/tools_environment_permissions.md`).
- `process lifecycle and cancellation boundaries` are part of the tools/environment domain rather than just Wave 02 or Wave 03 spillover.
  - BigAI traces rely heavily on run/wait/kill boundaries and show failed kill attempts (`research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`).
  - DeepAgents and KIRA both show cancellation behavior as a cross-family failure boundary (`research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`, `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`).

What changed because of contradiction review

- I am not treating the earlier Gemini `blocked` verdict as active.
  - That verdict was produced before the trajectory lane existed and is now outdated (`tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/contradiction_analyst__gemini.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_failure_analyst.md`).
- I am not promoting `environment discovery` as a strong cross-family mechanism card.
  - The current evidence supports it only as an exploratory candidate because the direct trajectory signal is uneven and partly reconstruction-heavy (`tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/contradiction_analyst.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/contradiction_analyst__claude.md`).
- I am not promoting robust `permission safety`.
  - The stronger current synthesis is narrower:
    - source and formal evidence show real policy and capability doctrine,
    - informal evidence shows strong operational pressure and policy-runtime mismatch,
    - required trajectories do not yet show end-to-end robust approval enforcement across families.
- I am not promoting A-Evolve as a fully trajectory-reconciled Wave 05 family.
  - The strongest current statement is:
    - A-Evolve materially strengthens the source-side Wave 05 picture,
    - but it remains source-backed without required-trajectory reconciliation in this packet.
- I am carrying the missing `headless_terminal.md` case-study path as a governance warning, not as a synthesis blocker.
  - The wave has sufficient lane coverage for principal synthesis, but support-track closure is still imperfect (`tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/brief.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/contradiction_analyst.md`).

Promoted mechanism cards

```text
MECHANISM_CARD
- mechanism_id: cwd_workdir_and_path_contract
- name: CWD Workdir And Path Contract
- short_definition: Tool execution remains reliable only when cwd, workdir, and path-target assumptions are explicit, validated, and kept inside the intended workspace boundary.
- mechanism_family: workspace_targeting_and_path_control
- harness_area: tools_and_environment
- location_in_harness: tool wrapper, runner workspace contract, path validator, and execution precondition checks
- operational_shape: The harness or agent resolves paths relative to an explicit workspace root, validates target paths, discourages implicit shell-state drift, and treats wrong cwd or wrong path shape as a first-class failure boundary.
- problem_it_addresses: wrong-target edits, import failures, and false negatives caused by executing in the wrong directory or with the wrong path semantics
- direct_observations:
  - BigAI `cancel-async-tasks` fails under `/tmp` and succeeds after moving execution back to `/app`.
  - DeepAgents exposes explicit path validation and absolute-path doctrine.
  - KIRA validates cwd against resolved workspace paths.
- inferred_behavior:
  - This is a real cross-family mechanism family and should be preserved as its own block or contract surface in the local harness.
- evidence_paths:
  - research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt
  - research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/utils.py
  - research/sources/codebases/deepagents/libs/cli/deepagents_cli/agent.py
  - research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_manager.py
  - tracking/collab/stage_02_synthesis/informal_cluster_dossiers/tools_environment_permissions.md
- evidence_types:
  - trajectory
  - source_code
  - informal_cluster
- source_families:
  - BigAI
  - deepagents
  - KIRA
- task_regimes_observed:
  - cancel async tasks
  - headless terminal
  - workspace/path targeting
- likely_failure_modes_addressed:
  - wrong-target edits
  - import path failure
  - cwd drift
  - path canonicalization failure
- failure_role:
  - preventive
- contradictory_or_complicating_evidence:
  - Current trajectory pressure is strongest in a few slices, especially BigAI `cancel-async-tasks`; broader saturation still needs optional long-tail pressure.
- interaction_notes:
  - Interacts strongly with tool gateway design, sandbox roots, workspace hygiene, and approval-policy scope.
- likely_tradeoffs:
  - Stronger path fences can reduce accidental damage but can also make legitimate cross-root workflows harder.
- simplicity_note:
  - Minimal-sufficient and important to preserve.
- likely_eval_implications:
  - Add evals that distinguish functional success from wrong-target success and mixed absolute-relative path failures.
- likely_variant_axes:
  - absolute-path-only doctrine
  - root-fenced relative paths
  - relaxed shell-state pathing
- confidence:
  - high
- open_questions:
  - What is the minimal local harness interface that enforces cwd/path integrity without making normal tool usage too rigid?
```

```text
MECHANISM_CARD
- mechanism_id: layered_permission_policy_and_capability_boundary
- name: Layered Permission Policy And Capability Boundary
- short_definition: Whether an action can run technically and whether it is approved to run are separate mechanism layers that must be modeled independently.
- mechanism_family: policy_vs_capability_separation
- harness_area: permissions_and_sandbox
- location_in_harness: tool policy layer, sandbox boundary, approval controller, and runtime capability checks
- operational_shape: The harness distinguishes capability boundaries such as filesystem, process, or network containment from policy decisions such as allow/deny/ask and HITL approval.
- problem_it_addresses: false safety assumptions when sandboxing, approval policy, and actual runtime behavior diverge
- direct_observations:
  - DeepAgents local-shell execution is unsandboxed while CLI policy and interrupts still govern execution approval.
  - KIRA shows explicit allow/deny/ask policy in KiraClaw and a separate bypass-permissions path in KIRA-Slack.
  - Formal and informal evidence both show that approval doctrine and runtime enforcement are not automatically equivalent.
- inferred_behavior:
  - Permission handling must stay split between capability and authorization if the local harness is going to remain honest and swappable.
- evidence_paths:
  - research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/local_shell.py
  - research/sources/codebases/deepagents/libs/cli/deepagents_cli/agent.py
  - research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/engine.py
  - research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/bot_call_detector/agent.py
  - tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md
  - tracking/collab/stage_02_synthesis/informal_cluster_dossiers/tools_environment_permissions.md
- evidence_types:
  - source_code
  - literature_dossier
  - informal_cluster
- source_families:
  - deepagents
  - KIRA
  - a-evolve
  - public issue clusters
- task_regimes_observed:
  - shell execution
  - MCP and tool routing
  - sandbox and approval policy
- likely_failure_modes_addressed:
  - policy bypass
  - false confidence from sandbox rhetoric
  - approval flow drift
  - runtime-policy mismatch
- failure_role:
  - preventive
- contradictory_or_complicating_evidence:
  - Required trajectories do not yet show strong end-to-end approval-policy enforcement across families.
  - Informal evidence is strong on failure pressure but concentrated in a few public systems.
- interaction_notes:
  - Interacts strongly with tool gateway scaling, subagent boundaries, path-root fences, and browser/tool trust surfaces.
- likely_tradeoffs:
  - Stronger approval doctrine can reduce unsafe actions but can also create prompt storms and autonomy collapse if poorly scoped.
- simplicity_note:
  - Important anti-collapse card; do not merge it into generic sandboxing.
- likely_eval_implications:
  - Separate evals for capability containment, policy correctness, and approval-volume usability.
- likely_variant_axes:
  - no approval layer
  - allow-deny-ask shell policy
  - HITL approval envelopes
  - per-tool approval scopes
- confidence:
  - high
- open_questions:
  - Which local harness surface should own authorization, and how do we prove policy-to-runtime equivalence?
```

```text
MECHANISM_CARD
- mechanism_id: terminal_first_minimal_tooling_baseline
- name: Terminal-First Minimal Tooling Baseline
- short_definition: A disciplined shell-plus-file baseline remains the strongest directly supported tooling substrate in the required Wave 05 evidence, with richer browser or MCP stacks acting as conditional extensions rather than default superiority.
- mechanism_family: minimal_tool_substrate
- harness_area: execution_and_tools
- location_in_harness: default tool block, orientation expectations, and execution substrate selection
- operational_shape: The harness defaults to a narrow terminal-and-files tool surface, adding richer browser, image, or MCP surfaces only when task demands justify them.
- problem_it_addresses: prestige-driven overgrowth of tool surfaces without evidence they improve reliability on the target regime
- direct_observations:
  - DeepAgents required slices succeed or meaningfully progress through terminal and file tools.
  - KIRA required slices stay terminal-first even when `image_read` is used as a selective uplift.
  - BigAI required slices are shell-heavy rather than browser-first.
- inferred_behavior:
  - The current evidence still favors a simple default substrate and argues against treating richer tooling stacks as the default best answer.
- evidence_paths:
  - research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt
  - research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt
  - research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt
  - research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt
  - tracking/collab/stage_02_synthesis/informal_cluster_dossiers/tools_environment_permissions.md
- evidence_types:
  - trajectory
  - informal_cluster
- source_families:
  - deepagents
  - KIRA
  - BigAI
- task_regimes_observed:
  - headless terminal
  - cancel async tasks
  - extract moves from video
- likely_failure_modes_addressed:
  - tool-sprawl overload
  - browser prestige overreach
  - hidden substrate instability
- failure_role:
  - preventive
- contradictory_or_complicating_evidence:
  - A-Evolve and KiraClaw source show richer substrate capacity than the required trajectories exercise.
  - Browser reliability pressure is currently issue-heavy rather than trajectory-saturated.
- interaction_notes:
  - Interacts with tool gateway scaling, path discipline, and permission envelopes.
- likely_tradeoffs:
  - A narrow baseline can underperform on tasks that genuinely need vision, browser, or remote tool ecosystems.
- simplicity_note:
  - Minimal-sufficient and important to keep visible.
- likely_eval_implications:
  - Compare simple shell-plus-file baselines directly against browser-heavy and MCP-heavy variants on the same tasks.
- likely_variant_axes:
  - terminal plus file only
  - terminal plus selective image/tool uplift
  - terminal plus MCP expansion
  - browser-heavy substrate
- confidence:
  - high
- open_questions:
  - Which exact task regimes justify leaving the minimal baseline?
```

```text
MECHANISM_CARD
- mechanism_id: process_lifecycle_and_cancellation_boundary_control
- name: Process Lifecycle And Cancellation Boundary Control
- short_definition: Wait, kill, cancellation, and cleanup semantics form a real tools-domain mechanism surface rather than a minor implementation detail.
- mechanism_family: process_and_interrupt_control
- harness_area: execution_and_recovery
- location_in_harness: process manager, interrupt controller, tool wrappers, and cleanup checks
- operational_shape: The harness exposes explicit process lifecycle controls and treats cancellation behavior, cleanup, and process-state ambiguity as part of the execution substrate.
- problem_it_addresses: dead hangs, orphaned processes, misread cancellation outcomes, and cleanup drift after interrupts
- direct_observations:
  - BigAI relies on explicit run/wait/kill shell job controls and shows kill-state friction in required slices.
  - DeepAgents and KIRA both show cancellation behavior as a recurring task-family failure surface.
- inferred_behavior:
  - Process lifecycle control should stay visible as a swappable harness block concern rather than being hidden under generic execution.
- evidence_paths:
  - research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt
  - research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt
  - research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt
  - research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_support_permission_boundary_cases.md
- evidence_types:
  - trajectory
  - support_artifact
- source_families:
  - BigAI
  - deepagents
  - KIRA
- task_regimes_observed:
  - cancel async tasks
  - extract moves from video
- likely_failure_modes_addressed:
  - dead process wait
  - no-such-process cleanup errors
  - cleanup drift under cancellation
  - interrupt ambiguity
- failure_role:
  - mixed
- contradictory_or_complicating_evidence:
  - Current saturation is concentrated in cancellation-heavy regimes and is not yet universal across all tool-use tasks.
- interaction_notes:
  - Interacts with permission boundaries, cleanup-confirmed completion, and terminal substrate design.
- likely_tradeoffs:
  - Richer lifecycle controls increase observability but can enlarge the agent's control surface and failure modes.
- simplicity_note:
  - Strongly wave-relevant, but still regime-weighted.
- likely_eval_implications:
  - Add evals that stress wait/kill correctness, cleanup after interrupts, and no-such-process handling.
- likely_variant_axes:
  - simple blocking shell only
  - wait and kill APIs
  - interrupt-aware cleanup checks
  - full async process supervision
- confidence:
  - high
- open_questions:
  - Which parts of this surface belong in execution blocks versus recovery blocks in the local harness?
```

Candidate mechanism not yet promoted

- `environment_discovery_as_stable_cross_family_mechanism`
  - Evidence supports it as a real concern and likely precondition surface.
  - Evidence is still too uneven across direct trajectories to promote it as a stable Wave 05 family.
  - Keep this candidate `exploratory`.

Support-track updates

- Already present and usable:
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/tool_use_and_gateways.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md`
  - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/tools_environment_permissions.md`
  - Wave 03 and Wave 04 source-system dossiers remain usable support surfaces for Wave 05 source reconciliation.
- Still incomplete or only partially aligned:
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md` is still missing.
  - Wave 05 uses existing `extract_moves_from_video.md` and `cancel_async_tasks.md` case studies as carry-forward support, but they are still Wave 03 case-study artifacts rather than fresh Wave 05 rewrites.
  - Wave 05 source-system dossier refreshes were not completed as separate support-track updates in this pass.

What still requires another wave

- Wave 05 does not settle `planning`, `orchestration`, or `subagent interaction` as mechanism families. Those belong in Wave 06.
- Wave 05 does not settle browser watchdog or restart-safe browser recovery as a stable mechanism family.
- Wave 05 does not settle robust approval-policy enforcement behaviorally across families.
- Wave 05 does not settle A-Evolve trajectory-side standing inside this domain because the current packet is source-heavy for that family.
- Wave 05 does not complete `mechanism_map`.

Local harness implications

- The local harness should separate at least four concerns rather than collapsing them:
  - tool gateway selection and schema exposure
  - execution capability boundary or sandbox substrate
  - approval and permission policy
  - cwd/workdir/path contract
- The Wave 05 evidence still favors keeping a simple terminal-plus-files baseline visible in `blocks/tools/` rather than making browser or large MCP stacks the default.
- The local harness likely needs explicit process-lifecycle surfaces for wait, kill, and interrupt-aware cleanup instead of hiding them inside a generic execution loop.
- Current local harness code under `blocks/` and `runner/` is still mostly interface and stub surface in this area (`blocks/tools/raw_bash.py`, `blocks/tools/structured.py`, `blocks/tools/reasoning_tools.py`, `runner/agent.py`, `runner/docker_sandbox.py`).
  - So these implications are directional design pressure, not implementation parity claims.

Coverage not yet used

- `research/sources/docs/src_doc_1ebb8bf0aacd/artifact.txt`
- `research/sources/docs/src_doc_695f1b9755d4/artifact.txt`
- `research/sources/docs/src_doc_78e1a708df4a/artifact.txt`
- `research/sources/papers/papers_text/2603.00324.txt`
- `research/sources/papers/papers_text/2603.03329.txt`
- `research/sources/papers/papers_text/src_pap_2531fb990b03.txt`
- `research/sources/issues/src_iss_677a876a6ea9/artifact.txt`
- `research/sources/issues/src_iss_7ea08b4fb93c/artifact.txt`
- `research/sources/issues/src_iss_6bbe542bed6c/artifact.txt`
- `research/sources/informal/anthropic_long_running_harness.md`
- optional long-tail cwd/worktree pressure in `research/sources/trajectories/*/git-multibranch/**`

Priority sources not yet read

- `research/sources/docs/src_doc_1ebb8bf0aacd/artifact.txt`
- `research/sources/papers/papers_text/2603.00324.txt`
- `research/sources/issues/src_iss_677a876a6ea9/artifact.txt`
- `research/sources/informal/anthropic_long_running_harness.md`
- optional long-tail pressure in `research/sources/trajectories/*/git-multibranch/**`

Next governed step

- Run Wave 05 checklist adjudication.
- Keep these warnings explicit for checklist:
  - BigAI remains `behavioral reconstruction`
  - permission safety remains under-evidenced at trajectory level
  - environment discovery remains `exploratory`
  - A-Evolve remains source-backed rather than trajectory-reconciled in this wave
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md` is still missing
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` remains empty, so direct path accounting still outranks organizer routing
