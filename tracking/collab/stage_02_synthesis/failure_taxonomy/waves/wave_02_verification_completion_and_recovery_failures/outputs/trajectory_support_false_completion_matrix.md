# Wave 02 Trajectory Support False Completion Matrix

Purpose
- Inventory required-wave runs for mismatch between in-run completion/verification signaling and final bundled verifier acceptance.

Legend
- `in_run_signal`: what trajectory visibly claims (`finish_verification`, explicit success narration, `mark_task_complete`, none)
- `final_gate`: bundle-level `reward.txt` + `ctrf.json`
- `mismatch`: `yes` when in-run signal suggests success but final gate is failing or absent

| system | task | run | in_run_signal | final_gate | mismatch | evidence |
|---|---|---|---|---|---|---|
| BigAI | cancel-async-tasks | `98b7...` | `finish_verification: PASSED` + success narrative | reward `0`; ctrf `1 failed` (`test_tasks_cancel_above_max_concurrent`) | yes | `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz` |
| deepagents | cancel-async-tasks | `ca5a...` | verified narrative + local checks (`max_running 2`, cleanup prints) | reward `0`; ctrf `1 failed` (`test_tasks_cancel_above_max_concurrent`) | yes | `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`, `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz` |
| terminus-kira | extract-moves-from-video | `3df8...` | repeated `mark_task_complete` + completion reasoning | reward `0`; ctrf `1 failed` (`test_solution_content_similarity`) | yes | `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`, `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd.tar.gz` |
| BigAI | extract-moves-from-video | `953d...` | no visible `finish_verification`; heavy extraction narration only | reward `0`; ctrf `1 failed` (`test_solution_content_similarity`) | partial (verifier omission) | `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`, `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d.tar.gz` |
| BigAI | db-wal-recovery | `47f2...`, `a1ed...`, `e150...` | `finish_verification: PASSED` | reward `1`; ctrf all passed | no | `research/sources/trajectories/BigAI/db-wal-recovery/*-traj.txt`, `research/sources/trajectories/BigAI/db-wal-recovery/*.tar.gz` |

Notes
- This matrix is run-inventory support only; promoted claims remain in `trajectory_failure_analyst.md`.
- BigAI remains `behavioral reconstruction` even when mismatch is directly visible in trajectories + verifier bundles.
