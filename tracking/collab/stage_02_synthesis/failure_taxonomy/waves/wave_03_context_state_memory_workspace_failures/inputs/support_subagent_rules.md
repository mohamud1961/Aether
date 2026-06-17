# Failure Taxonomy Wave 03 Support Sub-Agent Rules

Use bounded support sub-agents only for narrow support work.

Rules

- Support sub-agents are helpers, not canonical failure analysts.
- Main lane agents still own synthesis and final claim wording.
- Every support output must be written as an explicit artifact in this wave's `outputs/` directory.
- Support artifacts can organize evidence, cluster issues, build matrices, and map source links, but they do not become final failure claims by themselves.
- Do not overwrite another lane's files.
- If concurrent files appear in the wave output directory, treat them as parallel governed work unless they collide with your assigned write scope.
- Expect the repo to have unrelated dirty files from concurrent Deep Synthesis work.
- Do not stop for a dirty worktree alone.
- Edit only your assigned Wave 03 output file and any explicitly assigned support dossier file.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with your assigned write scope.

Recommended support artifacts

- trajectory lane:
  - `trajectory_support_context_workspace_failure_matrix.md`
  - `trajectory_support_memory_state_drift_cases.md`
- codebase lane:
  - `codebase_support_context_state_failure_map.md`
  - `codebase_support_workspace_persistence_map.md`
- literature lane:
  - `literature_support_context_memory_failure_cluster.md`
- informal lane:
  - `informal_support_context_workspace_failure_cluster.md`
- optional eval lane if reactivated:
  - `eval_support_state_contract_map.md`

Allowed support task shapes

- per-run context/state/workspace failure matrixing
- workspace/repo/branch/path drift inventories
- source mapping for session persistence, workspace state, context compaction, memory stores, logging, and recovery handoff
- paper grouping around context management, memory, workspace artifacts, state persistence, compaction, and retrieval failure
- issue and postmortem clustering around stale memory, context overflow, session resume, branch/path corruption, and workspace drift

Stop conditions

- stop once the requested matrix, cluster, route map, or file-discovery task is complete
- stop if the task begins drifting into full synthesis or final failure-card writing
- stop and report if your work would require editing another lane's main output
- stop and report if the assigned output path is already being actively edited by another agent
