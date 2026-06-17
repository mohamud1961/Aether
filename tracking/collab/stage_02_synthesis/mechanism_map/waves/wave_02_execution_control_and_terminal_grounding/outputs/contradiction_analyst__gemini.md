DEEP_SYNTHESIS_CONTRADICTION_OUTPUT
- artifact: mechanism_map
- overall_verdict: pass_with_warnings
- preflight_scope_confirmed:
  yes: This is a vertical mechanism-domain wave for execution_control_and_terminal_grounding.
  yes: All four required first-pass analysts (trajectory, codebase, literature, informal) completed their assignments and anchored their claims properly.
- preflight_planned_read_order:
  1. Review trajectory behavioral claims for execution control.
  2. Cross-reference against codebase source-reconstruction to verify implementation.
  3. Validate against formal literature (Terminal-Bench, OPENDEV) definitions.
  4. Pressure with informal/issue reports on sandbox and session fragility.
- preflight_critical_sources_selected:
  `trajectory_failure_analyst.md`
  `codebase_source_reconstruction_analyst.md`
  `literature_papers_docs_analyst.md`
  `informal_issues_postmortems_analyst.md`
- preflight_coverage_risks:
  BigAI remains source-opaque; all mechanisms assigned to BigAI are `behavioral reconstruction` or formal doc claims, lacking empirical source validation.
- preflight_likely_blind_spots:
  Deep inspection of archived `src_cod_*` families is still pending.
  BigAI's true low-level terminal substrate remains unseen.
- preflight_blockers: none. The blind-parallel quartet is fully present and provides enough cross-lane pressure to safely synthesize the wave.
- coverage_used:
  `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst.md`
  `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst.md`
  `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/literature_papers_docs_analyst.md`
  `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/informal_issues_postmortems_analyst.md`
- coverage_not_yet_used:
  `research/sources/codebases/src_cod_*/artifact.zip`
  `research/sources/papers/papers_text/2602.07274.txt`
  `research/sources/trajectories/*/db-wal-recovery/*-traj.txt` (only partially read)
- evidence_classes_touched:
  trajectories
  mirrored codebases
  papers
  docs
  informal sources
  issues
  postmortems
- priority_sources_not_yet_read:
  Full extraction of `src_cod_*` codebases.
  Harbor `Terminus2` underlying implementation for KIRA.
- supported_findings:
  Execution control is not a monolithic architecture across families. It splits into at least two distinct source-backed regimes: 1) KIRA's tmux/keystroke session loops, and 2) DeepAgents/a-evolve's discrete command executors.
  BigAI's planner/executor/verifier role split is strongly supported by trajectories and formal docs, though it lacks codebase backing.
  Terminal-Bench scoring is outcome-driven and benchmark-invisible to execution control mechanics (like PTY and cleanup), which means harnesses are optimizing for execution safety mechanisms that aren't explicitly graded.
  Informal/issue pressure (e.g., compaction hangs, sandbox bypasses) strongly supports the trajectory finding that execution control is highly brittle and cannot be assumed to be a "solved" substrate.
- unsupported_or_overclaimed_findings:
  The assumption that a trajectory solving a PTY task means the harness uses a PTY. The Codebase analyst properly contradicted the Trajectory analyst's PTY-like finding for DeepAgents: DeepAgents uses `subprocess.run(shell=True)` and the agent itself builds a PTY inside the workspace.
  Strong durable resume/checkpointing claims in informal sources remain aspirational; issue lanes show these features routinely corrupt state or hang, and they are largely absent from the core source/trajectory anchors.
- missing_evidence_classes:
  None for this wave. The quartet executed effectively.
- reconciliation_failures:
  None structural. The codebase analyst cleanly intercepted and corrected the trajectory analyst's potential over-read of DeepAgents' PTY behavior.
- coverage_blind_spots:
  BigAI source implementation.
  Performance of these harnesses under strict formal sandbox (most trajectory runs appear to run with loose or easily bypassed sandboxes as noted in the issues lane).
- required_repairs_before_acceptance:
  Update the principal synthesis to explicitly separate the "tmux/PTY session" family (KIRA) from the "discrete shell execution" family (DeepAgents, a-evolve).
  Ensure BigAI claims remain explicitly tagged as `behavioral reconstruction` in the cumulative synthesis.
- optional_pressure_tests:
  Read the unread BigAI `db-wal-recovery` trajectories to see if verifier-driven control degrades identically to KIRA's direct-loop failure.
- confidence:
  high