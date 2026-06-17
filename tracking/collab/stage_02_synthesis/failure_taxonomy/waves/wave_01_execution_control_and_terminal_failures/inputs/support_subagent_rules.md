# Failure Taxonomy Wave 01 Support Sub-Agent Rules

Use bounded support sub-agents only for narrow support work.

Rules

- Support sub-agents are helpers, not canonical failure analysts.
- Main lane agents still own synthesis and final claim wording.
- Every support output must be written as an explicit artifact in this wave's `outputs/` directory.
- Support artifacts can organize evidence, cluster issues, build matrices, and map source links, but they do not become final failure claims by themselves.
- Do not overwrite another lane's files.
- If concurrent files appear in the wave output directory, treat them as parallel governed work unless they collide with your assigned write scope.

Recommended support artifacts

- trajectory lane:
  - `trajectory_support_failure_timeline.md`
  - `trajectory_support_terminal_failure_matrix.md`
- codebase lane:
  - `codebase_support_execution_failure_map.md`
  - `codebase_support_interrupt_cancellation_map.md`
- literature lane:
  - `literature_support_failure_pressure_cluster.md`
- informal lane:
  - `informal_support_timeout_false_success_cluster.md`
- optional eval lane:
  - `eval_support_benchmark_failure_contract_map.md`

Allowed support task shapes

- run inventory and per-run failure matrixing
- timeout and stall clustering
- source-link gathering for specific failure claims
- subsystem mapping for interrupt, kill, wait, timeout, cleanup, and verifier boundaries
- paper grouping around benchmark blindness, verifier omission, and replay limitations
- issue and postmortem clustering around false success, prompt storms, cancellation drift, and repo-state corruption

Stop conditions

- stop once the requested matrix, cluster, route map, or file-discovery task is complete
- stop if the task begins drifting into full synthesis or final failure-card writing
- stop and report if your work would require editing another lane's main output
