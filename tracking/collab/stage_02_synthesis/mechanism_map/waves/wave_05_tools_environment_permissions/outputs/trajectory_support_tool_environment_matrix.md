# Wave 05 Trajectory Support: Tool and Environment Matrix

## Scope
- wave: `mechanism_map / wave_05_tools_environment_permissions`
- lane: `trajectory/failure analyst`
- required trajectory slices covered:
  - `research/sources/trajectories/deepagents/headless-terminal/`
  - `research/sources/trajectories/deepagents/extract-moves-from-video/`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/`
  - `research/sources/trajectories/terminus-kira/headless-terminal/`
  - `research/sources/trajectories/terminus-kira/extract-moves-from-video/`
  - `research/sources/trajectories/terminus-kira/cancel-async-tasks/`
  - `research/sources/trajectories/BigAI/headless-terminal/`
  - `research/sources/trajectories/BigAI/extract-moves-from-video/`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/`

## Run-Level Matrix
- run: `deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
  - tool surface observed: `execute` (5), `edit_file` (3), `read_file` (2), `write_file` (1), `grep` (1)
  - substrate: terminal and file tools only
  - env discovery signal: explicit startup `environment_context` with `Current Directory: /app`
  - cwd/workdir discipline: strong `/app` anchoring in task files and edits
  - permission/sandbox signal: sandbox context is explicit in prompt text; no approval/escalation workflow exposed in the run
  - key failure/friction signal: none dominant in this slice
  - evidence:
    - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`

- run: `deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
  - tool surface observed: no sustained tool sequence (early abort)
  - substrate: incomplete (run abort)
  - env discovery signal: not enough observable sequence
  - cwd/workdir discipline: unknown in this run
  - permission/sandbox signal: unknown in this run
  - key failure/friction signal: immediate `CancelledError`
  - evidence:
    - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`

- run: `deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - tool surface observed: `execute` (5), `read_file` (1), `write_file` (1)
  - substrate: terminal-first with inline Python execution
  - env discovery signal: low explicit discovery in trajectory text; execution stays local
  - cwd/workdir discipline: stable around task file import path (`from run import run_tasks`)
  - permission/sandbox signal: no explicit approval boundary shown
  - key failure/friction signal: cancellation and cleanup semantics repeatedly tested
  - evidence:
    - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`

- run: `terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
  - tool surface observed: `bash_command` (16), `mark_task_complete` (2)
  - substrate: terminal-only
  - env discovery signal: prompt includes terminal state and strict task-complete protocol
  - cwd/workdir discipline: commands consistently scoped to `/app`
  - permission/sandbox signal: root-system `pip install` warning explicitly reported
  - key failure/friction signal: intermediate verification failure (`FileNotFoundError`) before closure
  - evidence:
    - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`

- run: `terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
  - tool surface observed: `bash_command` (64), `image_read` (4), `mark_task_complete` (3)
  - substrate: hybrid terminal + vision tool
  - env discovery signal: repeated environment/tool probing and dependency setup
  - cwd/workdir discipline: work remains `/app`-anchored with iterative scripts
  - permission/sandbox signal: package and venv churn plus module import mismatch visible
  - key failure/friction signal: `ModuleNotFoundError: No module named 'cv2'`, long OCR loop interruptions
  - evidence:
    - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`

- run: `terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - tool surface observed: `bash_command` (13), `mark_task_complete` (3)
  - substrate: terminal-only
  - env discovery signal: targeted test construction around runtime cancellation model
  - cwd/workdir discipline: tests and implementation iterated in `/app`
  - permission/sandbox signal: no explicit external approval boundary in trace
  - key failure/friction signal: cleanup interruption under repeated cancel behavior, then refactor/testing loops
  - evidence:
    - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`

- run: `BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt` (behavioral reconstruction context)
  - tool surface observed: `run_shell_command` (48), `kill_shell_command` (1), `save_plan` (2), plus lifecycle closure calls
  - substrate: shell command orchestration with controller lifecycle hooks
  - env discovery signal: initial dependency probe fails (`ModuleNotFoundError: pexpect`) then environment setup proceeds
  - cwd/workdir discipline: terminal-centric, `/app`-oriented execution
  - permission/sandbox signal: no explicit approval doctrine shown in this slice
  - key failure/friction signal: missing dependency and process lifecycle handling
  - evidence:
    - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`

- run: `BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt` (behavioral reconstruction context)
  - tool surface observed: `run_shell_command` (25), `wait_shell_command` (47), `kill_shell_command` (2), `save_plan` (1)
  - substrate: asynchronous shell job orchestration
  - env discovery signal: long-run command monitoring via explicit wait tool
  - cwd/workdir discipline: shell-job IDs and waits dominate state handling
  - permission/sandbox signal: none explicit; governance is via tool-level job controls
  - key failure/friction signal: repeated wait/kill cycles indicate load-bearing process-control boundary
  - evidence:
    - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`

- run: `BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt` (behavioral reconstruction context)
  - tool surface observed: `run_shell_command` (59), `save_plan` (3), lifecycle closure calls
  - substrate: shell-heavy async experimentation
  - env discovery signal: present but mostly implicit through iterative shell tests
  - cwd/workdir discipline: primarily `/app` shell workflow
  - permission/sandbox signal: no explicit approval flow shown
  - key failure/friction signal: cancellation behavior exploration dominates
  - evidence:
    - `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`

- run: `BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt` (behavioral reconstruction context)
  - tool surface observed: `run_shell_command` (30), `interact_with_shell` (14), `kill_shell_command` (1), `write_file` (6), `save_plan` (2), lifecycle calls
  - substrate: mixed asynchronous shell API plus direct interactive shell
  - env discovery signal: explicit friction detection around import path and signal model
  - cwd/workdir discipline: failed `/tmp` test (`No module named 'run'`) then shift into `/app`
  - permission/sandbox signal: process kill boundary and signal semantics are load-bearing
  - key failure/friction signal: import path mismatch, kill/no-process signal, cancellation/KeyboardInterrupt model drift
  - evidence:
    - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`

- run: `BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt` (behavioral reconstruction context)
  - tool surface observed: `run_shell_command` (62), `save_plan` (4), lifecycle closure calls
  - substrate: shell command orchestration
  - env discovery signal: startup message includes explicit task directory and team-space paths
  - cwd/workdir discipline: `/app` baseline plus `.work/space` references
  - permission/sandbox signal: none explicit in trajectory mechanics
  - key failure/friction signal: cancellation handling strategy ambiguity under runtime differences
  - evidence:
    - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`

## Cross-Run Structural Signals
- Distinct tool gateway families are already visible behaviorally:
  - DeepAgents: compact command/file-tool loop.
  - Terminus-KIRA: batch shell with explicit completion gate and optional `image_read`.
  - BigAI (behavioral reconstruction): shell job API with explicit run/wait/kill/interact controls and role-lifecycle closures.
- Minimal-sufficient baseline remains valid:
  - terminal and file tools under stable cwd discipline can solve required tasks without browser-first substrate.
- Permission boundary evidence is present but thin:
  - strong claims of permission safety are not supportable from these slices alone.
