TRAJECTORY_SUPPORT_ARTIFACT
- artifact: trajectory_support_failure_timeline
- wave: wave_01_execution_control_and_terminal_failures
- purpose: time-ordered failure and recovery signal map for required trajectory slices
- scope_paths:
  - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
  - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
  - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
- timeline:
  - phase: early termination / coverage loss
    events:
      - `deepagents/extract-moves`: immediate `CancelledError`; no recovery loop visible.
    attribution_note: evidence gap, not direct family failure conclusion.
  - phase: lifecycle stress with progressive hardening
    events:
      - `terminus-kira/cancel-async`: early tests show `Cleanups executed: 0`; later stress case triggers `BaseException ... CancelledError`; eventual suite passes.
      - `deepagents/cancel-async`: immediate inline checks for concurrency and cleanup pass in one run.
      - `BigAI/cancel-async`: repeated verifier cycles; strongest slice (`d799`) gates final acceptance on both logic and delivery cleanliness.
    attribution_note: cancellation semantics are cross-family failure-prone until hardened by stronger tests and cleanup checks.
  - phase: recovery grounding versus drift
    events:
      - `deepagents/db-wal`: WAL fix, artifact emit, then direct postcondition validation (`json_length`, `db_length`, `keys_ok`, `match_db`).
      - `BigAI/db-wal`: backup-first + decrypt + verifier pass loops; explicit delivery-directory checks before closure.
      - `terminus-kira/db-wal`: target path loss (`main.db-wal` absent), host/overlay exploration, mount denial, `/app` structure mutation, no visible closure artifact.
    attribution_note: recovery success depends on maintaining artifact grounding and bounded control loops.
  - phase: extraction completion contest
    events:
      - `terminus-kira/extract-moves`: unresolved `201/230/262` count contradiction under completion pressure.
      - `BigAI/extract-moves`: high process supervision (`wait/kill` loops) but no visible final verifier event in inspected slice.
    attribution_note: extraction family is currently insufficiently saturated for strong closure attribution.
- confidence:
  - high for run-local event ordering and visible failure/recovery signals
  - medium for prevalence and cross-family generalization
