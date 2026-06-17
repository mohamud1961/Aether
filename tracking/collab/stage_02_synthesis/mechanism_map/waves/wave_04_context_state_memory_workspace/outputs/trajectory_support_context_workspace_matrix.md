DEEP_SYNTHESIS_SUPPORT_OUTPUT
- artifact: mechanism_map / wave_04_context_state_memory_workspace / trajectory_support_context_workspace_matrix
- wave: wave_04_context_state_memory_workspace
- calling_lane: trajectory/failure analyst
- support_task_type: trajectory context/workspace matrix
- bounded_scope_confirmed: yes
- files_or_paths_read:
  - research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt
  - research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt
  - research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt
  - research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt
  - research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt
  - research/sources/trajectories/BigAI/break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt
  - research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt
  - research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt
  - research/sources/trajectories/BigAI/custom-memory-heap-crash/11834f22-09ea-4bc7-9a11-68f574976a10-traj.txt
  - research/sources/trajectories/deepagents/custom-memory-heap-crash/aa903d02-9999-4aa2-8d70-3a73a4eb6d8c-traj.txt
  - research/sources/trajectories/terminus-kira/custom-memory-heap-crash/3c178f63-b5da-4ffa-b4c3-225d919b72ec-traj.txt
- structured_findings:
  - |
    | run slice | context retention | artifact continuity | workspace / branch hygiene | explicit memory write / retrieval | compaction / handoff signal |
    | --- | --- | --- | --- | --- | --- |
    | BigAI git-multibranch | Strong planner/executor split; planner keeps a todo list and assigns work; executors do not share memory unless asked | Strong: `/app` cleanup, `/git/project` reset/recreation, `/var/www/main` and `/var/www/dev` cleanup are treated as state to preserve or sanitize | Strong: branch hygiene and clean bare-repo state are explicitly managed | Weak: no durable memory store; state is mostly planner todo updates and tool-history references | Strong: repeated todo completion, verifier feedback, cleanup, and final summary are explicit handoff markers |
    | BigAI git-multibranch (second slice) | Same family, but the later run emphasizes re-verification and cleanup more than planning | Strong: final report says delivery dir cleaned and repo sanitized | Strong: repository state is actively reset to satisfy verifier concerns | Weak: no long-term memory, just run-local history and plan state | Strong: the run is re-opened after verifier feedback and then closed with a clean-state report |
    | deepagents git-multibranch | Strong: todo list is updated in-place and reused across steps | Strong: reusable `/app/test_deploy.sh` captures the workflow and reruns it end-to-end | Moderate: repo and services are left in a verified deployed state; branch hygiene is present but less central than in BigAI | Weak: memory is represented by todo status and saved script, not by a persistent memory subsystem | Strong: completion comes from todo completion plus rerun of the full clone/push/curl workflow |
    | terminus-kira git-multibranch | Strong but narrow: JSON command batches carry an explicit checklist every turn | Weak to moderate: no durable workspace artifact is emphasized in the sampled windows | Moderate: task directory and delivery-directory rules are explicit, but branch/worktree state is not a major visible surface | Weak: no persistent memory store; the checklist and prior terminal output are the state surface | Strong: every response is checklist-driven, so compaction is mostly manual summarization into JSON |
    | BigAI break-filter-js-from-html | Strong: the run recovers deleted test content from tool history / prior logs and preserves the exploit payload | Very strong: `/app/test_outputs.py` is restored after accidental deletion; temp test files are removed afterward | Moderate: workspace cleanup is explicit, but branch hygiene is not relevant here | Moderate: retrieval is from executor/tool history and `.pyc` cross-checks, not from durable model memory | Strong: explicit recovery from mistake, re-verification, and cleanup of temporary files |
    | BigAI break-filter-js-from-html (second slice) | Same family; the later verification confirms the restored file and clean `/app` state | Very strong: the restored test file is treated as part of the deliverable state, not a throwaway artifact | Moderate: cleanup is focused on `/app`, not on branches | Moderate: restore-by-log and bytecode cross-check are the only explicit retrieval signals | Strong: the run ends only after the restored file and payload are verified cleanly |
    | deepagents break-filter-js-from-html | Weak to moderate: state is local and short-lived, centered on `/app/out.html` and `/app/test_outputs.py` | Strong for the immediate task: out.html is written in place and test script is rerun | Weak: no branch/worktree state | Weak: no durable memory surface; file I/O and test rerun do the work | Moderate: one-shot creation, test, and stop; little evidence of multi-step state recovery |
    | terminus-kira break-filter-js-from-html | Weak to moderate: path correction and rerun of the Python test function are the main state controls | Moderate: temporary test files are deleted, and the required deliverable remains | Weak: no branch/worktree hygiene is central | Weak: state lives in the current file set and the live checklist, not in a memory subsystem | Strong: explicit deletion of extraneous files is followed by a focused rerun and verification |
    | BigAI custom-memory-heap-crash | Strong: the run retains crash context across compiler/source exploration and gdb backtrace analysis | Strong: source patches and final user.cpp edits are part of the state surface; the release crash is reproduced before fix | Weak: no branch/worktree axis | Moderate: retrieval comes from `/build` source, backtrace, and later verification notes; not from durable memory | Strong: the task cycles through reproduce -> trace -> source patch -> verify -> leak-check |
    | deepagents custom-memory-heap-crash | Strong: the run keeps the crash root cause in view across release/debug builds, gdb, source patch, and Valgrind | Strong: `/app/user.cpp` is the only final edit surface; the fix is verified in both build modes | Weak: no branch/worktree axis | Moderate: source reconstruction from `/build` and runtime traces is explicit, but still not durable memory | Strong: repeated compile/run/Valgrind loops plus final zero-leak validation close the loop |
    | terminus-kira custom-memory-heap-crash | Weak to moderate: the sampled window shows iterative experiments in `user.cpp` and release/debug runs, but the end-state is thin | Moderate: the run keeps the edited file in focus, but the sampled lines stop before a crisp final fix report | Weak: no branch/worktree axis | Weak to moderate: the only visible retrieval is from file edits and live run output; no stable memory store is shown | Weak to moderate: the sampled window shows repeated trials and Valgrind output, but not a fully saturated recovery narrative |
- unresolved_gaps:
  - The sampled trajectory text does not show a durable memory subsystem in any family; most "memory" behavior is really planner state, checklist state, saved scripts, or retrieval from prior tool logs.
  - Branch/worktree hygiene is only load-bearing in the git-multibranch family and in BigAI cleanup; it should not be generalized to the HTML or heap-crash slices.
  - The terminus-kira custom-memory slice is thinner in the sampled window than the other crash slices, so its end-state should be treated cautiously until the main lane confirms the later lines.
  - Archive members inside the `.tar.gz` bundles were not expanded in this support pass, so any finer-grained state transitions inside those bundles remain unread here.
- handoff_notes_for_calling_lane:
  - Use this matrix as evidence that explicit workspace artifacts often substitute for long-term memory: todo lists, saved test scripts, restored files, and clean repo state are the recurring state surfaces.
  - Treat BigAI behavioral claims as behavior-only unless another lane anchors them in source.
  - The minimal-sufficient baseline to keep visible is "explicit artifact continuity with little or no durable memory machinery"; richer memory rhetoric is not supported by these trajectory slices alone.
  - For the main synthesis, the strongest cross-run contrast is between runs that preserve and replay artifacts exactly and runs that only keep enough live state to finish the immediate task.
- not_promoted_claims:
  - No claim that any family exposes a general-purpose long-term memory architecture.
  - No claim that branch hygiene is universal across the corpus.
  - No claim that restart/resume is established as a stable behavioral family from these slices alone.
  - No claim that the terminus-kira custom-memory slice is fully saturated in the sampled window.
- support_artifacts_used: none
- support_artifacts_requested_or_deferred:
  - deferred: branch / worktree state table
  - deferred: run-to-source link map
  - deferred: memory-write and stale-memory case table
  - deferred: archive expansion for `.tar.gz` members
- coverage_register_updates_needed:
  - none from this support artifact alone; the main lane should decide whether the matrix justifies any wave-level coverage-register note
- required_dossier_updates:
  - deferred to the main lane; likely updates if promoted include the three trajectory case studies named in the wave brief and the relevant source-system dossiers
- output_path: tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_support_context_workspace_matrix.md
