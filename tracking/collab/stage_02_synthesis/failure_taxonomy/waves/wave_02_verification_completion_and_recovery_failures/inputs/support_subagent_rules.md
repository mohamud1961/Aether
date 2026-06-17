# Failure Taxonomy Wave 02 Support Sub-Agent Rules

Use bounded support sub-agents only for narrow support work.

Rules

- Support sub-agents are helpers, not canonical failure analysts.
- Main lane agents still own synthesis and final claim wording.
- Every support output must be written as an explicit artifact in this wave's `outputs/` directory.
- Support artifacts can organize evidence, cluster issues, build matrices, and map source or benchmark links, but they do not become final failure claims by themselves.
- Do not overwrite another lane's files.
- If concurrent files appear in the wave output directory, treat them as parallel governed work unless they collide with your assigned write scope.
- Expect the repo to have unrelated dirty files from concurrent Deep Synthesis work.
- Do not stop for a dirty worktree alone.
- Edit only your assigned Wave 02 output file and any explicitly assigned support dossier file.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with your assigned write scope.

Recommended support artifacts

- trajectory lane:
  - `trajectory_support_false_completion_matrix.md`
  - `trajectory_support_recovery_failure_matrix.md`
- codebase lane:
  - `codebase_support_verifier_recovery_failure_map.md`
  - `codebase_support_completion_cleanup_map.md`
- literature lane:
  - `literature_support_verification_recovery_failure_cluster.md`
- informal lane:
  - `informal_support_false_completion_recovery_cluster.md`
- eval lane:
  - `eval_support_verifier_benchmark_contract_map.md`

Allowed support task shapes

- per-run false-completion and recovery-failure matrixing
- run-to-verifier/replay/cleanup link gathering
- source mapping for verifier boundaries, recovery paths, cleanup logic, final acceptance, and replay assumptions
- paper grouping around verification, replay, benchmark blindness, checkpoint/restore, and recovery limits
- issue and postmortem clustering around false success, stale completion, verifier omission, rollback/resume failure, and cleanup-confirmed invalid states
- benchmark-contract and grader/replay route maps

Stop conditions

- stop once the requested matrix, cluster, route map, or file-discovery task is complete
- stop if the task begins drifting into full synthesis or final failure-card writing
- stop and report if your work would require editing another lane's main output
- stop and report if the assigned output path is already being actively edited by another agent
