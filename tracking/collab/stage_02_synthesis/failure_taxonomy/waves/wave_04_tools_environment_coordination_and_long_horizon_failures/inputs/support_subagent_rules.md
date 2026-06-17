# Failure Taxonomy Wave 04 Support Sub-Agent Rules

Use bounded support sub-agents only for narrow support work.

Rules

- Support sub-agents are helpers, not canonical failure analysts.
- Main lane agents still own synthesis and final claim wording.
- Every support output must be written as an explicit artifact in this wave's `outputs/` directory.
- Support artifacts can organize evidence, cluster issues, build matrices, map source links, and inventory runs, but they do not become final failure claims by themselves.
- Do not overwrite another lane's files.
- If concurrent files appear in the wave output directory, treat them as parallel governed work unless they collide with your assigned write scope.
- Expect the repo to have unrelated dirty files from concurrent Deep Synthesis work.
- Do not stop for a dirty worktree alone.
- Edit only your assigned Wave 04 output file and any explicitly assigned support dossier file.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with your assigned write scope.

Recommended support artifacts

- trajectory lane:
  - `trajectory_support_tool_coordination_failure_matrix.md`
  - `trajectory_support_long_horizon_failure_timeline.md`
- codebase lane:
  - `codebase_support_tool_environment_failure_map.md`
  - `codebase_support_orchestration_failure_map.md`
- literature lane:
  - `literature_support_tools_orchestration_failure_cluster.md`
- informal lane:
  - `informal_support_long_horizon_tooling_failure_cluster.md`
- optional eval lane if reactivated:
  - `eval_support_benchmark_time_contract_map.md`

Allowed support task shapes

- per-run tool/environment/orchestration failure matrixing
- timeout-heavy and long-horizon run inventories
- source mapping for tool gateways, approval policy, path-root doctrine, process lifecycle, replanning, delegation, and verifier gating
- paper grouping around permissions, environment control, orchestration, delegation, and long-horizon degradation
- issue and postmortem clustering around browser/tool instability, approval mismatch, coordination stalls, delegation drift, cancellation failure, and timeout pressure

Stop conditions

- stop once the requested matrix, cluster, route map, timeline, or file-discovery task is complete
- stop if the task begins drifting into full synthesis or final failure-card writing
- stop and report if your work would require editing another lane's main output
- stop and report if the assigned output path is already being actively edited by another agent
