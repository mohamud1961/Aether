# Trajectory Support Source Links

- artifact: `mechanism_map`
- role: `trajectory support source links`
- scope: `wave_02_execution_control_and_terminal_grounding`
- status: support artifact only, not final mechanism synthesis

## claim_label: KIRA tmux/keystroke session control and completion gating

- direct_source_observations:
  - [`research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`](/Users/mohamud/Downloads/harnesseng/research/sources/codebases/KIRA/terminus_kira/terminus_kira.py) imports `TmuxSession`, sends verbatim keystrokes with `send_keys`, polls `capture_pane()`, and uses a `__CMDEND__<seq>__` marker to exit early when output is ready.
  - [`research/sources/codebases/KIRA/README.md`](/Users/mohamud/Downloads/harnesseng/research/sources/codebases/KIRA/README.md) explicitly advertises marker-based polling and "Smart Completion Verification" with a double-confirmation checklist.
  - [`research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_tools.py`](/Users/mohamud/Downloads/harnesseng/research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_tools.py) exposes background `exec` plus `process` actions for `poll`, `log`, `kill`, and `clear`.
  - [`research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_manager.py`](/Users/mohamud/Downloads/harnesseng/research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_manager.py) tracks sessions, marks killed sessions, refreshes status by polling the child process, and terminates with `SIGTERM`/`SIGKILL` when needed.
- reconciliation_with_trajectory_claims:
  - These sources reconcile cleanly with the trajectory reading that KIRA is a session-style harness rather than a plain stateless shell loop.
  - The completion gate is source-backed: the agent asks for `task_complete`, then emits a separate confirmation checklist before final grading begins.

## claim_label: DeepAgents discrete command/file execution, timeout, and interrupt gating

- direct_source_observations:
  - [`research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/local_shell.py`](/Users/mohamud/Downloads/harnesseng/research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/local_shell.py) executes commands with `subprocess.run(..., shell=True)` on the host, returns combined stdout/stderr, and enforces per-command timeouts.
  - The same file states that `virtual_mode` only affects filesystem semantics and "does NOT restrict shell commands," which is the key non-PTY / non-sandbox caveat.
  - [`research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py`](/Users/mohamud/Downloads/harnesseng/research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py) documents the built-in tool set as planning, filesystem, shell `execute`, and `task` subagents, and says `interrupt_on` can pause execution for human approval.
  - [`research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/filesystem.py`](/Users/mohamud/Downloads/harnesseng/research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/filesystem.py) emphasizes filesystem-first tooling, read-before-edit behavior, and an `execute` tool with optional timeout overrides.
  - [`research/sources/codebases/deepagents/libs/evals/deepagents_harbor/deepagents_wrapper.py`](/Users/mohamud/Downloads/harnesseng/research/sources/codebases/deepagents/libs/evals/deepagents_harbor/deepagents_wrapper.py) shows Harbor wrapping DeepAgents with sandbox metadata, confirming the execution path is mediated but still command-oriented.
- reconciliation_with_trajectory_claims:
  - These sources support the trajectory claim that DeepAgents behaves as a discrete command-and-file executor rather than a PTY-native session harness.
  - The visible source also supports the timeout/interrupt pressure seen in trajectories without requiring a hidden terminal session model.

## claim_label: Visible local harness execution surfaces are still scaffold-level

- direct_source_observations:
  - [`blocks/tools/raw_bash.py`](/Users/mohamud/Downloads/harnesseng/blocks/tools/raw_bash.py) is currently only a one-line docstring for a single unrestricted bash tool.
  - [`blocks/execution/flat_loop.py`](/Users/mohamud/Downloads/harnesseng/blocks/execution/flat_loop.py) is currently only a one-line docstring for a simple while-not-done loop.
  - [`runner/agent.py`](/Users/mohamud/Downloads/harnesseng/runner/agent.py) is still a responsibilities-only stub describing block wiring and Docker execution.
  - [`evals/verification_eval.py`](/Users/mohamud/Downloads/harnesseng/evals/verification_eval.py) is still a tests/verification placeholder, not an implemented verifier.
- reconciliation_with_trajectory_claims:
  - The local repo currently provides design pressure and interface placeholders, but not an implemented competing execution-control stack.
  - This means local harness files can be compared against the external harness families, but they should not be over-read as evidence of an already-real control mechanism.

## claim_label: BigAI remains behavioral reconstruction only

- direct_source_observations:
  - No mirrored BigAI harness source path was available in the read set for this follow-up.
  - The trajectory lane and prior wave outputs therefore remain the only direct evidence surface for BigAI behavior in this domain.
- reconciliation_with_trajectory_claims:
  - BigAI can still support execution-control comparisons at the behavior level, but this support file cannot link it to implementation source.
  - Any BigAI mechanism reading here should stay tagged `behavioral reconstruction` and should not be promoted to source-backed fact.

## follow-up_takeaways

- KIRA has the strongest visible source-backed terminal-session story in this wave.
- DeepAgents has the strongest visible source-backed discrete-command story in this wave.
- The local harness code is still too skeletal to close the loop against either family.
- BigAI is still useful for contrast, but only as trajectory pressure until mirrored source appears.
