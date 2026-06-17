# Wave 02 Trajectory Support Recovery Failure Matrix

Purpose
- Inventory required-wave recovery/resume outcomes and failure surfaces without collapsing model/harness/environment/contract causes.

| system | task | run | observed_recovery_loop | final_outcome | dominant_failure_surface | evidence |
|---|---|---|---|---|---|---|
| BigAI | cancel-async-tasks | `d799...` | visible fail-then-pass verifier loop (`FAILED` then `PASSED`) with cleanup/hygiene corrections | reward `1`, ctrf all passed | recovery succeeds after adding cleanup + stronger checks | `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603.tar.gz` |
| BigAI | cancel-async-tasks | `98b7...` | success narration and verifier pass in run | reward `0`, ctrf has failing edge case | incomplete recovery of edge-case contract (`cancel_above_max_concurrent`) | `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz` |
| deepagents | cancel-async-tasks | `ca5a...` | local checks cover running-task cleanup only (`cleaned [0, 1]`) | reward `0`, ctrf has failing edge case | partial recovery semantics; queued/above-limit cancellation contract not proven | `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`, `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz` |
| terminus-kira | db-wal-recovery | `3481...` | no bounded recovery closure visible; shifts into environment probing | reward `0`; verifier stderr shows `getcwd` / missing cwd | environment-state drift/recovery breakdown | `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`, `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz` |
| deepagents | extract-moves-from-video | `67dc...` | none; run aborts almost immediately (`CancelledError`) | reward `0`, ctrf 2 failed | thin/aborted trajectory prevents recovery attribution | `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`, `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8.tar.gz` |
| terminus-kira | extract-moves-from-video | `3df8...` | repeated completion attempts after OCR interruption (`KeyboardInterrupt`) | reward `0`, content-similarity failed | recovery retries did not converge to benchmark-grade output quality | `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`, `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd.tar.gz` |

Notes
- This matrix is a bounded support artifact and does not promote causal certainty by itself.
- BigAI rows remain `behavioral reconstruction`.
