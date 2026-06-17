# Trajectory Support Run Inventory

- Scope: selected Wave 02 task families only, across `deepagents`, `terminus-kira`, and `BigAI`.
- Method: inventory readable `*-traj.txt` runs and archive-only `*.tar.gz` runs in the selected task families, then flag archive-only BigAI variants that could still matter for judgment.

## Readable-text coverage

- `deepagents/headless-terminal`: `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
- `deepagents/cancel-async-tasks`: `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
- `deepagents/db-wal-recovery`: `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
- `deepagents/break-filter-js-from-html`: `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`
- `deepagents/git-multibranch`: `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
- `terminus-kira/headless-terminal`: `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
- `terminus-kira/cancel-async-tasks`: `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
- `terminus-kira/db-wal-recovery`: `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
- `terminus-kira/break-filter-js-from-html`: `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`
- `terminus-kira/git-multibranch`: `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
- `BigAI/headless-terminal`: `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
- `BigAI/cancel-async-tasks`: `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
- `BigAI/db-wal-recovery`: `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`, `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`, `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
- `BigAI/break-filter-js-from-html`: `research/sources/trajectories/BigAI/break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt`, `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
- `BigAI/git-multibranch`: `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`, `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`

## Archive-only coverage

- `BigAI/headless-terminal`: `research/sources/trajectories/BigAI/headless-terminal/955f47f3-f86f-4989-a975-1299ed63a173.tar.gz`, `research/sources/trajectories/BigAI/headless-terminal/b579b8e9-66a0-4d35-8e21-4333c7db1146.tar.gz`, `research/sources/trajectories/BigAI/headless-terminal/c4676385-d244-44f5-ae16-7bccd71bbc7c.tar.gz`
- `BigAI/cancel-async-tasks`: `research/sources/trajectories/BigAI/cancel-async-tasks/71ef0a56-0b53-4639-974a-0190139c059c.tar.gz`
- `BigAI/db-wal-recovery`: `research/sources/trajectories/BigAI/db-wal-recovery/8586f6b0-3d1c-4eee-86b8-eee44cfad6c5.tar.gz`, `research/sources/trajectories/BigAI/db-wal-recovery/aea97873-3af7-4954-8c4f-a32b01b7cc99.tar.gz`
- `BigAI/break-filter-js-from-html`: `research/sources/trajectories/BigAI/break-filter-js-from-html/6e8cb0c4-fcb1-4310-8f49-fd6505a405bd.tar.gz`, `research/sources/trajectories/BigAI/break-filter-js-from-html/76b82a2e-50bd-409b-97cf-1e244809da1b.tar.gz`
- `BigAI/git-multibranch`: `research/sources/trajectories/BigAI/git-multibranch/4faa9840-b48b-4bf0-a37d-303de24a0ac3.tar.gz`, `research/sources/trajectories/BigAI/git-multibranch/64b05d98-c740-48e3-b46b-378a858786ba.tar.gz`, `research/sources/trajectories/BigAI/git-multibranch/bfcf2260-b5c7-4fa4-9662-5da094854b87.tar.gz`

## Archive-only variants most likely to matter

- `BigAI/headless-terminal` archive trio: most likely to matter because this family is the strongest terminal-control comparison slice and the three unread variants are the only extra trials beyond the readable run.
- `BigAI/db-wal-recovery` archive duo: most likely to matter because recovery and task-state grounding are where hidden divergence would be expected if the readable slice were overfit.
- `BigAI/git-multibranch` archive trio: most likely to matter because repo-state hygiene and branch isolation are exactly the kind of behavior that can vary across extra runs without changing the headline pass/fail label.
- `BigAI/cancel-async-tasks/71ef0a56-0b53-4639-974a-0190139c059c.tar.gz`: most likely to matter as the only unread cancellation trial in a family with mixed visible failure pressure in the readable slice.
- Result of archive rescue: all inspected archive-only BigAI runs still returned reward `1.0` with passing verifier summaries, so they expand coverage but do not change the local pass/fail split.
