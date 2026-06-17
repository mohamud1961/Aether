# Wave 05 Trajectory Support: Permission and Boundary Cases

## Scope
- wave: `mechanism_map / wave_05_tools_environment_permissions`
- lane: `trajectory/failure analyst`
- purpose: isolate trajectory-visible boundary failures and near-failures tied to environment, permission, process, cwd/workdir, and substrate control

## Cases
- case_id: PB-01
  - boundary surface: explicit environment anchoring
  - observation: DeepAgents headless-terminal starts with `environment_context` that pins `Current Directory: /app` and discourages redundant environment probing.
  - inference: environment discovery is front-loaded as a boundary guard, not a byproduct.
  - confidence: high
  - weakness: one family slice, not cross-family by itself.
  - evidence:
    - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`

- case_id: PB-02
  - boundary surface: cwd/workdir path discipline
  - observation: BigAI cancel-async run fails `from run import run_tasks` in `/tmp` (`ModuleNotFoundError`) and then re-routes to `/app`.
  - inference: cwd/workdir is a hard correctness boundary for tool success; mis-anchored process launches produce immediate false negatives.
  - confidence: high
  - weakness: behavioral reconstruction for BigAI internals.
  - evidence:
    - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`

- case_id: PB-03
  - boundary surface: system package permission risk
  - observation: Terminus-KIRA headless-terminal installs dependencies as root and receives pip warning about broken permissions/system package manager conflicts.
  - inference: permission risk is operationally visible in trajectory output, even without an explicit approval gate mechanism.
  - confidence: high
  - weakness: warning alone does not prove subsequent corruption.
  - evidence:
    - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`

- case_id: PB-04
  - boundary surface: process lifecycle and kill semantics
  - observation: BigAI slices repeatedly use `wait_shell_command` and `kill_shell_command`; error traces include failed kill attempts (`No such process`) in cancellation experiments.
  - inference: process boundary control is a first-class mechanism surface, not just convenience tooling.
  - confidence: medium
  - weakness: sampled trajectories show symptoms, not full invariant enforcement policy.
  - evidence:
    - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`

- case_id: PB-05
  - boundary surface: interrupt and cancellation propagation
  - observation: DeepAgents extract-moves slice terminates with top-level `CancelledError`; KIRA and BigAI cancel-async slices spend substantial effort resolving cleanup behavior under cancellation and SIGINT.
  - inference: cancellation semantics are a recurrent failure boundary that can mimic tool failure or verification failure when not isolated.
  - confidence: high
  - weakness: concentrated in one benchmark family (`cancel-async-tasks`) plus one aborted extract run.
  - evidence:
    - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
    - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`

- case_id: PB-06
  - boundary surface: toolchain environment consistency
  - observation: Terminus-KIRA extract-moves run shows `ModuleNotFoundError: No module named 'cv2'` despite prior package installation and later venv usage.
  - inference: interpreter/environment mismatch is a practical boundary fault that can consume large run budget.
  - confidence: high
  - weakness: does not alone identify root cause (path, venv activation, or tool invocation mismatch).
  - evidence:
    - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`

## Boundary-Case Summary
- Boundaries that are strongly evidenced in trajectories:
  - cwd/workdir import path discipline
  - process wait/kill lifecycle control
  - cancellation semantics and cleanup behavior
  - interpreter/toolchain environment consistency
- Boundaries that remain weakly evidenced in this lane:
  - explicit sandbox approval policy mechanics
  - formal permission escalation contracts
