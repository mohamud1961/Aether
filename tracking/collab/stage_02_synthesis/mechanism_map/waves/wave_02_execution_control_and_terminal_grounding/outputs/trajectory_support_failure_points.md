# TRAJECTORY_SUPPORT_FAILURE_POINTS
- artifact: mechanism_map
- role: trajectory/failure support
- wave: wave_02_execution_control_and_terminal_grounding
- scope: selected readable runs plus a small archive rescue pass for BigAI only
- preflight_scope_confirmed: true. This is a bounded support pass for the execution-control / terminal-grounding domain, not a full resynthesis and not a source lane.
- preflight_planned_read_order:
  - wave packet and governance: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/brief.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/inputs/trajectory_followup_01_packet.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/inputs/lane_followup_plan.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/inputs/support_subagent_rules.md`
  - first-pass trajectory lane and contradiction pressure: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/contradiction_analyst.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/synthesis/principal_synthesis.md`, `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - readable trajectories for the selected task families
  - a small archive rescue pass for BigAI bundles only where unread variants could change the current failure / cleanup judgment
- preflight_critical_sources_selected:
  - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
  - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
  - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
  - `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
  - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
  - `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`
  - `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`
  - `research/sources/trajectories/BigAI/break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt`
  - `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
  - `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
  - `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
  - `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`
  - `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
  - archive rescues: `research/sources/trajectories/BigAI/headless-terminal/955f47f3-f86f-4989-a975-1299ed63a173.tar.gz`, `research/sources/trajectories/BigAI/git-multibranch/4faa9840-b48b-4bf0-a37d-303de24a0ac3.tar.gz`, `research/sources/trajectories/BigAI/cancel-async-tasks/71ef0a56-0b53-4639-974a-0190139c059c.tar.gz`
- preflight_coverage_risks:
  - BigAI remains behavior-only in this support lane; the archive rescue can confirm reward / test splits, but it cannot prove implementation substrate.
  - The readable trajectory sample is high-signal but not exhaustive over all unread archive variants.
  - `db-wal-recovery` and `break-filter-js-from-html` are especially sensitive to cleanup and restoration side effects, so a pass in one run does not imply the whole family is clean.
  - The sampled KIRA and DeepAgents traces are enough for failure-point comparison, but not enough to settle source-backed implementation questions.
- preflight_likely_blind_spots:
  - unread BigAI archive-only variants not needed for this pass
  - deeper source / eval / paper evidence, intentionally excluded from this support artifact
  - whether the observed failure points are family-typical beyond the selected runs
- preflight_blockers: []
- coverage_used:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/brief.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/inputs/trajectory_followup_01_packet.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/inputs/lane_followup_plan.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/inputs/support_subagent_rules.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/contradiction_analyst.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/synthesis/principal_synthesis.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
  - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
  - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz::{result.json,verifier/ctrf.json,agent/trajectory.json}`
  - `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
  - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
  - `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`
  - `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`
  - `research/sources/trajectories/BigAI/break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt`
  - `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
  - `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
  - `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
  - `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`
  - `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
  - `research/sources/trajectories/BigAI/headless-terminal/955f47f3-f86f-4989-a975-1299ed63a173.tar.gz`
  - `research/sources/trajectories/BigAI/git-multibranch/4faa9840-b48b-4bf0-a37d-303de24a0ac3.tar.gz`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/71ef0a56-0b53-4639-974a-0190139c059c.tar.gz`
- coverage_not_yet_used:
  - remaining unread archive-only variants under `research/sources/trajectories/{deepagents,terminus-kira,BigAI}/{headless-terminal,cancel-async-tasks,db-wal-recovery,break-filter-js-from-html,git-multibranch}/*.tar.gz`
  - mirrored source, papers/docs, informal/issues/postmortems, benchmark captures, and local harness code were not touched in this support pass
- evidence_classes_touched:
  - trajectories
  - archive bundles
  - wave governance and carry-forward artifacts
- priority_sources_not_yet_read:
  - `research/sources/trajectories/BigAI/headless-terminal/b579b8e9-66a0-4d35-8e21-4333c7db1146.tar.gz`
  - `research/sources/trajectories/BigAI/headless-terminal/c4676385-d244-44f5-ae16-7bccd71bbc7c.tar.gz`
  - `research/sources/trajectories/BigAI/break-filter-js-from-html/6e8cb0c4-fcb1-4310-8f49-fd6505a405bd.tar.gz`
  - `research/sources/trajectories/BigAI/break-filter-js-from-html/76b82a2e-50bd-409b-97cf-1e244809da1b.tar.gz`
  - `research/sources/trajectories/BigAI/git-multibranch/64b05d98-c740-48e3-b46b-378a858786ba.tar.gz`
  - `research/sources/trajectories/BigAI/git-multibranch/bfcf2260-b5c7-4fa4-9662-5da094854b87.tar.gz`
  - the unread deepagents and terminus-kira archive-only bundles under the same selected task families

run_inventory_extended
- headless-terminal
  - deepagents readable: `8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
  - terminus-kira readable: `a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
  - BigAI readable: `cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
  - archive-only inspected: `955f47f3-f86f-4989-a975-1299ed63a173.tar.gz`
- cancel-async-tasks
  - deepagents readable: `ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - terminus-kira readable: `8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - BigAI readable: `17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
  - BigAI archive rescue: `98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
  - archive-only inspected: `71ef0a56-0b53-4639-974a-0190139c059c.tar.gz`
- db-wal-recovery
  - deepagents readable: `0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
  - terminus-kira readable: `3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  - BigAI readable: `47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`, `a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`, `e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
- break-filter-js-from-html
  - deepagents readable: `802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`
  - terminus-kira readable: `eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`
  - BigAI readable: `4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt`, `4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
- git-multibranch
  - deepagents readable: `e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
  - terminus-kira readable: `80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
  - BigAI readable: `62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`, `baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`

per_run_analysis
- headless-terminal
  - DeepAgents `8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`: observation: the visible task is a direct `HeadlessTerminal` implementation with pexpect-like PTY behavior and local tests; no explicit failure pivot surfaced in the readable slice. interpretation: this is the simple direct-shell baseline, not a distress case.
  - Terminus-KIRA `a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`: observation: the run pivots through `pexpect`, an interactive `bash -i`, Ctrl+C tests, `.bashrc` sourcing, and a final test script that checks command execution, Ctrl+C, and startup-file sourcing (`:64`, `:78`, `:131`, `:153`, `:169`, `:177`). interpretation: the key recovery point is proving interactive control, not solving a hard failure.
  - BigAI `cec71502-c287-4257-9aba-4e33b3668881-traj.txt` plus archive `955f47f3-f86f-4989-a975-1299ed63a173.tar.gz`: observation: the agent repeatedly checks `read_nonblocking`, Ctrl+C, shell sourcing, cleanup of test artifacts, and final verifier output; the archive confirms `reward: 1.0` and `7/7` tests passed. interpretation: BigAI exposes more internal scrutiny around buffer handling and delivery cleanup, but no new failure point beyond the verification discipline itself.
- cancel-async-tasks
  - DeepAgents `ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`: observation: the run is explicitly framed with `STOP. You must verify`, then validates concurrency (`max_running 2`) and cleanup on cancellation / exception (`cleaned [0, 1]`, `cleaned ['fail', 'ok-1', 'ok-2']`). interpretation: the visible failure surface is the cancellation edge, but the run itself resolves it cleanly.
  - Terminus-KIRA `8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`: observation: the first test attempt yields `Max concurrent: 2` but `Cleanups executed: 0`, then a revised test prints `Task cancelled, starting cleanup...`, `Cleanup finished.`, and `Cleanups executed: 2`. interpretation: the main recovery pivot is fixing the cancellation / cleanup path so tasks already running can finish `finally` blocks.
  - BigAI `17f3a357-c55a-4171-af6a-510581362baa-traj.txt`: observation: the run hardens against `ExceptionGroup`, `KeyboardInterrupt`, `SystemExit`, self-cancellation, and semaphore release; the visible tests repeatedly confirm `cleanup_ran: 2` and the final verifier marks `PASSED`. interpretation: BigAI stresses the same cleanup doctrine more aggressively than DeepAgents, but still lands on a clean pass.
  - BigAI archive `98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`: observation: verifier summary is `5 passed, 1 failed`, `reward: 0.0`; the failing test is `test_tasks_cancel_above_max_concurrent` because stdout contains `Task started.` twice and no `Cleaned up.` lines. the agent trajectory nevertheless ends with `verification_result_status: PASSED` inside the internal verifier flow. interpretation: this is the strongest pass/fail divergence in the follow-up sample, and it specifically exposes cleanup under cancellation above the concurrency cap.
  - archive-only `71ef0a56-0b53-4639-974a-0190139c059c.tar.gz`: observation: `reward: 1.0`, no extra failure signal beyond the readable runs. interpretation: this archive did not change the judgment.
- db-wal-recovery
  - DeepAgents `0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`: observation: the visible slice mainly shows the verifier-driven `STOP. You must verify` checkpoint. interpretation: the excerpt does not expose a special failure mode; it reads like ordinary verification pressure rather than a recovery drama.
  - Terminus-KIRA `3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`: observation: the run first sees only 5 records from `main.db`, then discovers `main.db-wal` is missing, later interrupts a long-running `grep` with Ctrl+C (`:1480`, `:38`), and eventually probes mounts / overlay and Docker availability. interpretation: the failure point is loss of terminal control plus loss of WAL visibility; the run spends effort regaining control before any recovery path becomes plausible.
  - BigAI `47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`, `a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`, `e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`: observation: the readable runs move from “WAL missing / maybe already checkpointed” to backup + XOR decryption + extraction of all 11 records, with final verification passing. interpretation: BigAI’s failure point is not final correctness but the search / recovery phase; once the WAL is identified and decrypted, the run converges cleanly.
- break-filter-js-from-html
  - DeepAgents `802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`: observation: the task is framed as crafting a payload that survives `filter.py` and triggers `alert()` after filtering, followed by a verify step (`:133`). interpretation: no distinct failure point is visible in this readable slice; the key pivot is choosing the parser-differential payload.
  - Terminus-KIRA `eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`: observation: the readable slice shows the filter logic, the test harness, and a final `finish_verification` pass with the restored file visible at `/app/test_outputs.py`. interpretation: again, the main work is exploit selection and verification rather than recovery from a hard algorithmic failure.
  - BigAI `4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt`, `4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`: observation: the payload `<![CDATA[><script>alert(1)</script>]]>` is the bypass, but the important recovery pivot is restoring the accidentally deleted `/app/test_outputs.py`, rerunning `python /app/test_outputs.py`, and then finishing with `verification_result_status: PASSED` (`:7310`, `:7352`, `:7416`, `:8058`, `:8111`). interpretation: the strongest failure point is not the XSS bypass itself; it is verifier hygiene and side-effect recovery after the payload succeeds.
- git-multibranch
  - DeepAgents `e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`: observation: the agent explicitly plans `Start/verify sshd and nginx; test clone/push/deploy locally`, tracks todo completion, and reaches a clean push / verify path. interpretation: this is a straight-through deployment success case, with no major failure pivot visible in the sampled lines.
  - Terminus-KIRA `80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`: observation: the early strategy pivots from `git checkout` in a bare repo to `git archive | tar -x`, then the cloned test repo pushes `main` and `dev` and both endpoints return the expected branch content. interpretation: the main recovery point is choosing a deployment mechanism that avoids bare-repo checkout / index trouble.
  - BigAI `baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`, archive `4faa9840-b48b-4bf0-a37d-303de24a0ac3.tar.gz`: observation: the first verifier failure is about delivery cleanliness, specifically a dirty `/git/project` with leftover `main` / `dev` branches and a leftover `/app/test-repo`; the recovery step backs up `post-receive`, recreates `/git/project` as a fresh bare repo, restores the hook, and removes `/app/test-repo`, with the archive later showing `reward: 1.0`. interpretation: BigAI makes repo-state hygiene a first-class execution-control concern rather than a postscript.

shared_task_cross_system_comparison
- headless-terminal: all three systems need interactive terminal behavior, Ctrl+C handling, and shell-state verification; the visible divergence is that KIRA and BigAI explicitly stress PTY / interactive-session details, while DeepAgents looks more like a direct implementation-and-test loop.
- cancel-async-tasks: all three systems are gated by cleanup after cancellation; Terminus-KIRA exposes the weakest first attempt, and BigAI stresses the widest edge-case surface, including `KeyboardInterrupt`, `SystemExit`, and queue-above-concurrency cancellation.
- db-wal-recovery: all systems have to regain control after an opaque data-state problem; KIRA spends time on shell recovery and filesystem discovery, while BigAI actually reaches a successful WAL repair and extraction path.
- break-filter-js-from-html: all systems rely on a parser differential / bypass plus verification; BigAI alone surfaces an environment-cleanliness failure because the verifier file was deleted and had to be restored.
- git-multibranch: all systems need deploy + verify, but BigAI is the only one where repo-state cleanup and delivery-directory sanitation become explicit failure points that must be repaired before final verification.

pass_fail_divergence_analysis
- cancel-async-tasks: strongest split. `98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz` is a clean external failure (`reward: 0.0`, `5 passed / 1 failed`) even though the internal verifier trajectory ends with `verification_result_status: PASSED`. The failed test is exactly the above-max-concurrency cancellation cleanup case.
- git-multibranch: functional deployment can pass, but verifier cleanliness can still fail. BigAI’s first cleanup pass was rejected because the repo was dirty and `/app/test-repo` lingered; after reinitializing `/git/project` and removing the test repo, the run passes.
- break-filter-js-from-html: payload success is not enough. BigAI passes the XSS bypass, then fails verification until `/app/test_outputs.py` is restored; the failure is side-effect hygiene, not exploit logic.
- headless-terminal: no durable pass/fail split found in the sampled readable runs or the `955f...` archive rescue; the archive is a clean pass with `7/7` tests and `reward: 1.0`.
- db-wal-recovery: no durable pass/fail split found in the sampled runs; the main issue is control loss and data visibility, but the readable BigAI runs converge to success.

failure_point_comparison
- interactive shell tasks fail when control is lost or not proven: KIRA’s `db-wal-recovery` needs `Ctrl+C` to unblock a long `grep`, and headless-terminal spends its effort proving an interactive shell is actually interactive.
- async tasks fail when cleanup semantics are wrong: KIRA’s first `cancel-async-tasks` attempt leaves `Cleanups executed: 0`, and BigAI’s archive failure shows the above-max-concurrency cancellation path can skip cleanup entirely.
- recovery tasks fail when the artifact is gone or hidden: KIRA’s `db-wal-recovery` cannot see the WAL, then searches mounts and overlays; BigAI’s successful recovery only happens after backup + WAL repair.
- bypass tasks fail when verifier hygiene is violated: BigAI’s `break-filter-js-from-html` succeeds on the payload but fails when the restored test file is missing.
- deployment tasks fail when repo state is dirty, not when the endpoint content is wrong: BigAI’s `git-multibranch` first fails on leftover branches and stale test artifacts, then succeeds after a full repo reset.

archive_triage
- `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`: materially changed the judgment. It confirms the cancellation-cleanup split with an external reward of `0.0` and a `5/1` verifier result, while the agent trajectory still reports internal `PASSED`.
- `research/sources/trajectories/BigAI/headless-terminal/955f47f3-f86f-4989-a975-1299ed63a173.tar.gz`: no new failure signal. It is a clean `reward: 1.0` pass with `7/7` verifier tests passed.
- `research/sources/trajectories/BigAI/git-multibranch/4faa9840-b48b-4bf0-a37d-303de24a0ac3.tar.gz`: no new failure signal. It is a clean `reward: 1.0` pass and does not add a new cleanup or divergence case beyond the readable runs.
- `research/sources/trajectories/BigAI/cancel-async-tasks/71ef0a56-0b53-4639-974a-0190139c059c.tar.gz`: no new failure signal. It is also a clean `reward: 1.0` pass.

mechanism_hypotheses
- The repeated failure pattern across these tasks is not “the agent could not compute the answer”; it is “the agent had to regain or prove control over the execution environment, then prove the resulting state was clean enough for verification.”
- The strongest negative signal is usually a mismatch between apparent task success and verifier-visible state, especially when cleanup or delivery hygiene is part of the contract.
- BigAI’s planner / executor / verifier structure seems most visible when the verifier can expose a second-order failure: cleanup not run, stale branches left behind, or a required file accidentally deleted.

behavioral_reconstruction_caveats
- BigAI is still behavior-only in this support pass; the archive rescue confirms reward / test splits, but it does not prove the harness substrate.
- Failure absence is not coverage completeness. Several selected runs pass cleanly, but that only means they did not surface a distinct failure pivot in the sampled paths.
- The archive-only BigAI bundles that were not opened may still contain additional edge cases; they were left unread because they were unlikely to change the current support judgment.

followup_judgment
- This support pass is now deep enough to anchor the follow-up trajectory lane with concrete failure pivots, cleanup transitions, and one materially important pass/fail divergence archive.
- The remaining work for the main follow-up is synthesis and reconciliation, not more failure-point archaeology unless a new contradiction appears.
- The biggest unresolved asymmetry is still source reconciliation for BigAI and the remaining unread archive-only variants, but neither blocks this support artifact.
