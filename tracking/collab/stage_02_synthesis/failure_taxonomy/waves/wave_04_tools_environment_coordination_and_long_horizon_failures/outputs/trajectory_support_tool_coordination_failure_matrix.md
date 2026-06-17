# Trajectory Support Tool Coordination Failure Matrix (Wave 04)

Scope: required trajectory slices for Wave 04 trajectory lane.

| System / Run | Tool-gateway mismatch | Cwd/path/workspace mismatch | Permission/runtime mismatch | Process-lifecycle/cancellation breakdown | Delegation/handoff/replan mismatch | Timeout-heavy degradation | Evidence |
|---|---|---|---|---|---|---|---|
| BigAI `cancel-async` `17f3...` | Medium | High | Low | High | Medium | Low | `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt` |
| BigAI `cancel-async` `98b7...` | Low | Medium | Low | Medium | Medium | Low | `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt` |
| deepagents `cancel-async` `ca5a...` | Low | Low | Low | Medium | Low | Low | `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt` |
| KIRA `cancel-async` `8d55...` | Medium | Low | Low | High | Low | Low | `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt` |
| BigAI `headless-terminal` `cec7...` | Medium | Medium | Low | High | Medium | Medium | `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt` |
| deepagents `headless-terminal` `8359...` | Low | Low | Low | High | Low | Low | `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt` |
| BigAI `extract-moves` `953d...` | Medium | Medium | Medium | High | Medium | High | `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt` |
| KIRA `extract-moves` `3df8...` | High | Medium | Medium | Medium | Medium | Medium | `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt` |

Notes:
- BigAI rows are behavioral reconstruction only.
- `High` means directly evidenced repeated or decisive failure pressure in the run slice, not merely theoretical risk.
