CODEBASE_SOURCE_RECON_OUTPUT
- artifact: mechanism_map
- role: codebase/source-reconstruction analyst
- preflight_scope_confirmed: true, this is a vertical mechanism-domain wave focused on execution control, terminal grounding, interrupts, and stop rules.
- preflight_planned_read_order:
  1. KIRA mirrored source (process and session managers)
  2. deepagents mirrored source (skills, tools, locks)
  3. a-evolve mirrored source (seed workspace tools)
  4. quarantine/claw-code mirrored source (metadata)
  5. BigAI behavioral reconstruction analysis
- preflight_critical_sources_selected:
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_manager.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/session_manager.py`
  - `research/sources/codebases/deepagents/examples/deep_research/uv.lock`
  - `research/sources/codebases/a-evolve/seed_workspaces/swe/tools/bash.py`
  - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
- preflight_coverage_risks: deepagents execution core is largely opaque (runs via CLI / packages), limiting deep code inspection; claw-code is quarantined so we only have snapshot metadata for its execution mechanisms.
- preflight_likely_blind_spots: True PTY handling details in deepagents since the code is locked/compiled.
- preflight_blockers: none.
- coverage_used:
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_manager.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/session_manager.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/engine.py`
  - `research/sources/codebases/deepagents/examples/deep_research/uv.lock`
  - `research/sources/codebases/deepagents/AGENTS.md`
  - `research/sources/codebases/a-evolve/seed_workspaces/swe/tools/bash.py`
  - `research/sources/codebases/a-evolve/seed_workspaces/swe/tools/python.py`
  - `research/sources/codebases/quarantine/claw-code/src/reference_data/subsystems/skills.json`
  - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
- coverage_not_yet_used: deepagents and BigAI raw trajectories for interactive shells (deferred to trajectory analyst).
- evidence_classes_touched: mirrored codebases, relevant local analysis (BigAI trace).
- priority_sources_not_yet_read: `research/sources/trajectories/*` for specific execution slices.
- source_backed_mechanisms:
  - **KIRA**: Uses `BackgroundProcessManager` (`process_manager.py`) with standard `subprocess.Popen`, streaming `stdout`/`stderr` via background threads into a ring buffer. Does not use PTYs. Interrupts are handled via OS-specific process group kills (`os.killpg(pid, signal.SIGTERM)` followed by `SIGKILL`). This serves as the simple/minimal-sufficient contender.
  - **a-evolve**: Uses short-lived, blocking `subprocess.run` inside tool definitions (`bash.py`, `python.py`). Employs `subprocess.TimeoutExpired` for stuck processes. Lacks persistent PTY sessions.
  - **deepagents**: Evidence in `uv.lock` indicates the presence of `pexpect`, `ptyprocess`, and `pywinpty`, suggesting deepagents utilizes full PTY for interactive shell control. `AGENTS.md` notes that subprocesses spawned by background workers must explicitly set a timeout to prevent indefinite blocking.
- behavioral_reconstructions:
  - **BigAI**: Planner-first control is effectively universal. TTY and wait-heavy behavior is sparse and task-specific. Recovery after verifier rejection is a real recurring loop, indicating an external audit role rather than a tight monolithic loop. Executor fanout varies widely on harder tasks.
- subsystem_findings:
  - **PTY and interactive shell control**: Highly fragmented. KIRA and a-evolve avoid PTYs entirely, favoring simple pipes and blocking executions. deepagents introduces heavy PTY dependencies (`pexpect`) for terminal grounding.
  - **Interrupt and stuck-process recovery**: KIRA isolates this to the process manager with strong process-group termination (`killpg`). a-evolve relies purely on Python's built-in `subprocess.TimeoutExpired` during blocking executions.
  - **Replanning versus direct execution control**: KIRA strictly separates process orchestration (`process_manager.py`) from LLM-session queues (`session_manager.py`), ensuring execution control does not block the replanning loop.
- source_behavior_matches: a-evolve's simple timeout-based stuck-process handling directly aligns with its tooling constraints.
- source_behavior_mismatches: None definitively observed yet, pending trajectory analyst comparison.
- archive_or_visibility_limits: claw-code is quarantined, so its execution loop controls (like `skills/bundled/stuck.ts` and `skills/bundled/loop.ts` listed in metadata) cannot be statically verified. deepagents core execution logic is opaque in the open-source repo.
- confidence_notes:
  - High confidence in KIRA and a-evolve mechanisms due to visible implementation.
  - Medium confidence in deepagents PTY usage (inferred from dependency locks).
  - Low confidence in BigAI execution mechanics (labeled strictly as behavioral reconstruction).
- open_questions:
  - Does BigAI use a true PTY for headless-terminal tasks, or does it mock interactive prompts?
  - How does claw-code implement stuck process recovery in `stuck.ts`?
- next_hand_off_target: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/contradiction_analyst.md`