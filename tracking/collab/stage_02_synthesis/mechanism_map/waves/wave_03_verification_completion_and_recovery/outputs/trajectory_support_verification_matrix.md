DEEP_SYNTHESIS_SUPPORT_OUTPUT
- artifact: mechanism_map
- wave: wave_03_verification_completion_and_recovery
- calling_lane: trajectory/failure analyst
- support_task_type: verification/completion/recovery matrix
- bounded_scope_confirmed: yes
- files_or_paths_read:
  - `prompts/deep_synthesis_support_subagent_prompt.md`
  - `prompts/deep_synthesis_trajectory_failure_analyst_prompt.md`
  - `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
  - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
  - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
- structured_findings:
  - `Matrix rows are one-per-readable-run. "Outcome" states only what the visible text supports; uncaptured finishes stay marked as inconclusive.`
  - |
    | run | claimed completion signal | direct verification evidence | recovery / cleanup behavior | visible outcome |
    | --- | --- | --- | --- | --- |
    | deepagents/db-wal-recovery `0333...` | script prints `rows 11` and writes `/app/recovered.json` | direct `SELECT count(*)` returns `11` and JSON write completes | WAL is XOR-fixed in place; `finally`-style cleanup not central | success, 11 records recovered |
    | deepagents/cancel-async-tasks `ca5a...` | inline verification prints `max_running 2`, `cleaned [0, 1]`, `cleaned ['fail', 'ok-1', 'ok-2']` | concurrency and cleanup checks both pass | cancellation path explicitly awaits cleanup on `CancelledError` | success, cleanup behavior confirmed |
    | deepagents/extract-moves-from-video `67dc...` | `CancelledError` at step 2 | no completion or solution file evidence in the readable text | run terminates immediately on cancellation | failure / aborted, no output |
    | terminus-kira/db-wal-recovery `3481...` | no successful recovery marker in read text | `find` finds no WAL copy; `mount /dev/md1` denied | recovery degrades into overlay / device spelunking | failure, recovery not achieved in visible run |
    | terminus-kira/cancel-async-tasks `8d55...` | `task_complete` / `mark_task_complete` after tests and cleanup checks | `test_suite.py` reports `ALL TESTS PASSED` | cancellation tests show cleanup on running tasks | success, concurrency and cleanup validated |
    | terminus-kira/extract-moves-from-video `3df8...` | repeated `mark_task_complete` attempts despite unresolved command-count disagreement | `head`/`tail` confirms `/app/solution.txt` exists, but the readable run also preserves conflicting totals (`201`, `230`, `262`) | OCR pipeline is interrupted with `KeyboardInterrupt`; output file remains, but completion proof stays contested | contested completion signal, not a defended success case |
    | BigAI/db-wal-recovery `47f2...` | `Verification Report: PASSED` | decrypted WAL read by SQLite; 11 records checked; `recovered.json` inspected | backup restored after passive checkpoint side effects | success, 11 records and recovery verified |
    | BigAI/db-wal-recovery `a1ed...` | `verification_result_status: PASSED` and final report | backup copy, decrypted WAL, and `recovered.json` are checked | final state restored to keep `main.db-wal` present | success, verification passed |
    | BigAI/db-wal-recovery `e150...` | `Verification Report: PASSED` | `len(data)==11` / sorted-order checks and file checks appear | WAL and main DB are restored after inspection | success, recovery and cleanup verified |
    | BigAI/cancel-async-tasks `17f3...` | final text says the task is complete and all tests passed | `TaskGroup`/`Semaphore` design is exercised via tests | cleanup is explicitly awaited on cancellation | success, cleanup robustness verified |
    | BigAI/cancel-async-tasks `98b7...` | `verification_result_status: PASSED` / final completion text | SIGINT, cleanup, and concurrency tests are described and executed | queue-clearing and cancellation handling are emphasized | success, but with much broader exploratory text than the other runs |
    | BigAI/cancel-async-tasks `d799...` | `mark_task_complete` after tests pass | repeated test output shows `ALL TESTS PASSED` | cancellation cleanup is validated; delivery dir reported clean | success, cancellation coverage verified |
    | BigAI/extract-moves-from-video `953d...` | no final completion marker visible in the read slice | early steps show dependency installation and OCR pipeline setup only | work is still dominated by extraction attempts; no final cleanup signal seen | inconclusive in inspected slice, likely in-progress when read stopped |
- unresolved_gaps:
  - `BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt` was only partially read; no terminal completion marker was visible in the inspected slice.
  - `terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt` shows a failure-heavy recovery search, but the visible text does not prove whether a later unseen step recovered the WAL.
  - `deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt` is a hard cancellation artifact and does not offer a completion-completion pattern.
  - `terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt` produces a candidate output file, but the same readable run preserves unresolved disagreement between `201`, `230`, and `262`, so it should not be cited as defended completion proof without that contradiction.
- handoff_notes_for_calling_lane:
  - The strongest completion-proof pattern in this wave is not "agent says done"; it is "run-level verifier evidence plus artifact inspection."
  - The weakest coverage is on video-extraction runs, where cleanup/completion is either truncated or absent, so do not let them overrule the much stronger WAL and cancellation rows.
  - KIRA `db-wal-recovery` is the clearest negative counterexample: once the artifact disappears, the run shifts from repair to environment spelunking.
  - KIRA `extract-moves-from-video` should be treated as false-completion pressure, not as a defended success row, even though `/app/solution.txt` exists in the visible run.
- not_promoted_claims:
  - This is a support artifact only; it does not decide the mechanism card.
  - Rows marked `inconclusive` or `failure` should not be upgraded without direct trajectory evidence.
  - `BigAI/extract-moves-from-video` is intentionally left weaker than the recovered WAL and cancellation rows because the visible slice never reached a final verification point.
  - `terminus-kira/extract-moves-from-video` is intentionally not promoted as success because the visible run reaches completion pressure with unresolved command-count contradictions.
- output_path: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/trajectory_support_verification_matrix.md`
