TRAJECTORY_FAILURE_OUTPUT
- artifact: mechanism_map
- role: trajectory/failure analyst
- preflight_scope_confirmed:
  yes: this is a vertical mechanism-domain wave for `execution_control_and_terminal_grounding`, not a source-only or trajectory-only pass.
  yes: trajectory/failure evidence is the primary empirical anchor for this role.
  scope_for_this_pass: the explicit trajectory scope for this first-pass cross-run analysis is the five wave-targeted shared task families with cross-system availability under `research/sources/trajectories/{deepagents,terminus-kira,BigAI}/{headless-terminal,cancel-async-tasks,db-wal-recovery,break-filter-js-from-html,git-multibranch}/`.
  simple_contender_kept_visible: a direct single-agent PTY or shell loop with local verification remains a live contender beside planner or verifier-heavy control architectures; it is directly visible in `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`, `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`, and `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`.
- preflight_planned_read_order:
  1. Confirm wave scope and routing constraints from `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`, `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`, `tracking/collab/stage_02_synthesis/tracing_readiness/outputs/tracing_readiness.md`, `tracking/collab/stage_02_synthesis/mechanism_map/brief.md`, and the active wave brief.
  2. Read every readable `*-traj.txt` run in the five shared task families across DeepAgents, Terminus-KIRA, and BigAI so the cross-run comparison is exhaustive for readable text trajectories in scope.
  3. Inventory every remaining in-scope archive artifact under those same directories and mark them explicitly as not covered when not unpacked.
  4. Use `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md` only as a routing aid for BigAI role boundaries, not as implementation proof.
  5. Leave mirrored source, formal literature, informal sources, and eval-sidecar evidence to the same-wave companion analysts and keep those coverage gaps explicit.
- preflight_critical_sources_selected:
  readable trajectory set selected: all 21 readable `*-traj.txt` runs under the five in-scope task families listed in `run_inventory_covered`.
  contradiction-pressure slices selected: `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`, `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`, `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`, `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`, and the BigAI `db-wal-recovery` readable trio.
  behavior-reconstruction aid selected: `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`.
  source systems reserved for companion roles: `research/sources/codebases/deepagents/`, `research/sources/codebases/KIRA/`, `research/sources/codebases/quarantine/claw-code/`, `research/sources/codebases/a-evolve/`, and relevant `research/sources/codebases/src_cod_*/capture.json`.
- preflight_coverage_risks:
  this pass has complete readable-text coverage for the five selected task families, but not complete archive coverage; 32 in-scope `tar.gz` artifacts were inventoried and left unopened.
  BigAI remains source-opaque in this role, so any deeper controller explanation stays `behavioral reconstruction`.
  Terminus-KIRA readable trajectories are sometimes sparse at the tail, so some pass or fail judgments rely on the presence or absence of completion behavior already inspected in the full run, not just the final summary string.
  no same-wave source or benchmark reconciliation was performed in this role, so mechanism explanations remain behavior-first.
- preflight_likely_blind_spots:
  archive-only BigAI run variants that may contain additional divergences not surfaced in the readable text files.
  hidden scheduler or controller state inside BigAI beyond what planner or verifier handoffs expose.
  whether KIRA `db-wal-recovery` is family-typical or an especially bad single run.
  execution-control cases outside the five wave-targeted shared task families.
- preflight_blockers: []
- coverage_used:
  `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`
  `tracking/collab/stage_02_synthesis/tracing_readiness/outputs/tracing_readiness.md`
  `tracking/collab/stage_02_synthesis/mechanism_map/brief.md`
  `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/brief.md`
  `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_01_exploratory_anchor/synthesis/principal_synthesis.md`
  `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
  `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
  `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
  `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`
  `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
  `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
  `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`
  `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
  `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
  `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
  `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
  `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
  `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`
  `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`
  `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
  `research/sources/trajectories/BigAI/break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt`
  `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
  `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`
  `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
- coverage_not_yet_used:
  `research/sources/codebases/deepagents/`
  `research/sources/codebases/KIRA/`
  `research/sources/codebases/quarantine/claw-code/`
  `research/sources/codebases/a-evolve/`
  `research/sources/codebases/src_cod_*/capture.json`
  `research/sources/benchmarks/`
  `research/sources/papers/`
  `research/sources/docs/`
  `research/sources/informal/`
  `research/sources/issues/`
  `research/sources/postmortems/`
  `blocks/`
  `runner/`
  `evals/`
  `research/sources/trajectories/{deepagents,terminus-kira,BigAI}/{headless-terminal,cancel-async-tasks,db-wal-recovery,break-filter-js-from-html,git-multibranch}/*.tar.gz`
- evidence_classes_touched:
  trajectories
  relevant local analysis
  wave governance and coverage-routing artifacts
- priority_sources_not_yet_read:
  `research/sources/trajectories/BigAI/headless-terminal/955f47f3-f86f-4989-a975-1299ed63a173.tar.gz`
  `research/sources/trajectories/BigAI/headless-terminal/b579b8e9-66a0-4d35-8e21-4333c7db1146.tar.gz`
  `research/sources/trajectories/BigAI/headless-terminal/c4676385-d244-44f5-ae16-7bccd71bbc7c.tar.gz`
  `research/sources/trajectories/BigAI/cancel-async-tasks/71ef0a56-0b53-4639-974a-0190139c059c.tar.gz`
  `research/sources/trajectories/BigAI/db-wal-recovery/8586f6b0-3d1c-4eee-86b8-eee44cfad6c5.tar.gz`
  `research/sources/trajectories/BigAI/db-wal-recovery/aea97873-3af7-4954-8c4f-a32b01b7cc99.tar.gz`
  `research/sources/trajectories/BigAI/break-filter-js-from-html/6e8cb0c4-fcb1-4310-8f49-fd6505a405bd.tar.gz`
  `research/sources/trajectories/BigAI/break-filter-js-from-html/76b82a2e-50bd-409b-97cf-1e244809da1b.tar.gz`
  `research/sources/trajectories/BigAI/git-multibranch/4faa9840-b48b-4bf0-a37d-303de24a0ac3.tar.gz`
  `research/sources/trajectories/BigAI/git-multibranch/64b05d98-c740-48e3-b46b-378a858786ba.tar.gz`
  `research/sources/trajectories/BigAI/git-multibranch/bfcf2260-b5c7-4fa4-9662-5da094854b87.tar.gz`
  `research/sources/codebases/deepagents/`
  `research/sources/codebases/KIRA/`
  `research/sources/codebases/quarantine/claw-code/`
  `research/sources/benchmarks/`
- run_inventory_covered:
  direct-readable trajectories inspected in this wave:
  `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
  `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
  `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`
  `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
  `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
  `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`
  `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
  `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
  `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
  `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
  `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
  `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`
  `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`
  `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
  `research/sources/trajectories/BigAI/break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt`
  `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
  `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`
  `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
- run_inventory_not_covered:
  `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/BigAI/headless-terminal/955f47f3-f86f-4989-a975-1299ed63a173.tar.gz` — archive-only in-scope run; inventoried but not unpacked in this pass.
  `research/sources/trajectories/BigAI/headless-terminal/b579b8e9-66a0-4d35-8e21-4333c7db1146.tar.gz` — archive-only in-scope run; inventoried but not unpacked in this pass.
  `research/sources/trajectories/BigAI/headless-terminal/c4676385-d244-44f5-ae16-7bccd71bbc7c.tar.gz` — archive-only in-scope run; inventoried but not unpacked in this pass.
  `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/BigAI/cancel-async-tasks/71ef0a56-0b53-4639-974a-0190139c059c.tar.gz` — archive-only in-scope run; inventoried but not unpacked in this pass.
  `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/BigAI/db-wal-recovery/8586f6b0-3d1c-4eee-86b8-eee44cfad6c5.tar.gz` — archive-only in-scope run; inventoried but not unpacked in this pass.
  `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/BigAI/db-wal-recovery/aea97873-3af7-4954-8c4f-a32b01b7cc99.tar.gz` — archive-only in-scope run; inventoried but not unpacked in this pass.
  `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/BigAI/break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/BigAI/break-filter-js-from-html/6e8cb0c4-fcb1-4310-8f49-fd6505a405bd.tar.gz` — archive-only in-scope run; inventoried but not unpacked in this pass.
  `research/sources/trajectories/BigAI/break-filter-js-from-html/76b82a2e-50bd-409b-97cf-1e244809da1b.tar.gz` — archive-only in-scope run; inventoried but not unpacked in this pass.
  `research/sources/trajectories/BigAI/git-multibranch/4faa9840-b48b-4bf0-a37d-303de24a0ac3.tar.gz` — archive-only in-scope run; inventoried but not unpacked in this pass.
  `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/BigAI/git-multibranch/64b05d98-c740-48e3-b46b-378a858786ba.tar.gz` — archive-only in-scope run; inventoried but not unpacked in this pass.
  `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462.tar.gz` — paired archive for an already-read readable run; not unpacked because the readable text trajectory provided direct behavior evidence for this pass.
  `research/sources/trajectories/BigAI/git-multibranch/bfcf2260-b5c7-4fa4-9662-5da094854b87.tar.gz` — archive-only in-scope run; inventoried but not unpacked in this pass.
- coverage_claim:
  partial for wave scope: every readable `*-traj.txt` run in the five explicit shared task families was inspected, but 32 in-scope `tar.gz` run bundles were only inventoried and not unpacked, so this is not complete coverage for total wave trajectory artifacts.
- direct_behavior_observations:
  observation: DeepAgents and Terminus-KIRA both expose a direct grounded execution loop in `headless-terminal`, but they fail in different ways before converging. DeepAgents trips a daemon-thread shutdown cleanup problem during verification, while KIRA fails its first REPL-write check and then rewrites the test flow before cleaning artifacts and completing.
  evidence: `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`, `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
  confidence: high

  observation: BigAI `headless-terminal` visibly separates planner, executor, and verifier activity. The run includes a long-running shell experiment that needs `kill_shell_command`, repeated implementation or test revisions, and a final verifier pass that checks terminal, REPL, startup-file sourcing, and delivery cleanliness.
  evidence: `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`, `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
  confidence: high for the observed role separation; medium for controller internals because the mechanism explanation remains `behavioral reconstruction`.

  observation: In `cancel-async-tasks`, all three families reach passing outcomes, but KIRA and BigAI apply materially stronger cancellation pressure than the visible DeepAgents run. BigAI readable runs repeatedly verify cleanup under `CancelledError`, sibling-failure cancellation, `SystemExit`, `KeyboardInterrupt`, and clean delivery-state restoration.
  evidence: `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`, `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
  confidence: high

  observation: `db-wal-recovery` is the clearest success-vs-failure split in this wave scope. DeepAgents stays artifact-local, fixes the WAL, verifies 11 rows, and writes `recovered.json`. BigAI has three readable verifier-passed runs that also stay anchored to task artifacts and explicitly preserve or restore clean delivery state. Terminus-KIRA instead broadens into overlay, device, mount, and container forensics after the WAL disappears and no successful recovery artifact is visible in the readable run.
  evidence: `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`, `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`, `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`, `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`, `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
  confidence: high for the observed pass or fail split; medium-high for family-level interpretation because KIRA has one readable failure-heavy run here.

  observation: In `break-filter-js-from-html`, DeepAgents reaches a working bypass with the shortest visible path and no comparable workspace-integrity damage. Terminus-KIRA and BigAI both pass, but both also create intermediate harness or workspace hygiene problems that must be reverted or cleaned before completion.
  evidence: `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`, `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`, `research/sources/trajectories/BigAI/break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt`, `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
  confidence: high

  observation: In `git-multibranch`, DeepAgents and Terminus-KIRA both show benchmark-sufficient branch deployment. BigAI also passes, but readable runs make repo-state hygiene far more explicit: verifier pressure catches cleanliness or branch-isolation issues, then later steps reset repos and deploy directories before re-verification.
  evidence: `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`, `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`, `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`, `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
  confidence: high for the observed behavior; medium for any broader claim that BigAI is universally safer rather than simply more stressed in the visible runs.
- workflow_patterns:
  observation: a simple direct-execution family is real in this domain. DeepAgents and Terminus-KIRA often operate inside a single agent-visible shell loop with immediate local verification.
  inference: `execution_control` should not be mapped only to planner-heavy architectures; a direct grounded loop is a stable cross-family contender.
  evidence: `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`, `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`, `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  confidence: high

  observation: BigAI consistently exhibits planner or executor or verifier role separation in every readable task family in scope.
  inference: `workflow_role_separation` is a live mechanism family for BigAI, but deeper architecture claims remain `behavioral reconstruction` until source reconciliation lands.
  evidence: `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`, `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`, `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
  confidence: high for observed role separation; medium for scheduler or controller interpretation.

  observation: Across families, runs repeatedly re-ground themselves in shell output, file state, database state, or browser-visible behavior instead of only free-form reasoning.
  inference: terminal grounding in this wave is a mechanism family of repeated state checks, not just “tool access exists.”
  evidence: all readable trajectories listed in `run_inventory_covered`
  confidence: high
- verification_and_recovery_patterns:
  observation: stop rules are verification-coupled across families. DeepAgents receives explicit “stop and verify” pressure, KIRA reruns local failing checks before `mark_task_complete`, and BigAI often waits for a distinct verifier pass before plan closure.
  inference: the visible stop condition is rarely “I think I am done”; it is “the verifier-visible state now matches the task contract.”
  evidence: `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`, `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`, `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
  confidence: high

  observation: interrupt handling is a real control primitive. `Ctrl-C` is used positively in terminal tests, BigAI uses `kill_shell_command` when a shell experiment hangs, and KIRA uses `C-c` to recover terminal control after drifting into an interactive subshell.
  inference: interruptibility is load-bearing for this mechanism area, but it is not sufficient by itself to keep the broader task loop grounded.
  evidence: `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`, `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`, `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  confidence: high

  observation: cancellation recovery is explicitly cleanup-sensitive in the strongest runs. KIRA and BigAI both construct failing cases where naive cancellation returns too early or lets more work start after cancel.
  inference: “await cleanup before exit” belongs in execution-control and stop-rule cards, not only in async error-handling notes.
  evidence: `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
  confidence: high

  observation: repo-safe execution in the strongest visible slices includes reset and cleanup of the environment, not only the target code. BigAI git and db-wal runs explicitly restore clean delivery or repository state after verification activity.
  inference: repo-state-safe execution is broader than successful task output; it includes side-effect hygiene and re-runnability.
  evidence: `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`, `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`, `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`, `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
  confidence: high
- failure_candidates:
  candidate: terminal implementations can satisfy simple shell interaction while still failing on shutdown behavior or deeper interactive semantics.
  observation: DeepAgents hits a daemon-thread interpreter-shutdown cleanup failure, KIRA initially fails REPL behavior, and BigAI has to kill a hung shell experiment before converging.
  evidence: `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`, `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`, `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
  confidence: high

  candidate: naive cancellation loops can leak control by returning before cleanup or by allowing queued work to start after cancel.
  observation: KIRA and BigAI both build explicit adversarial tests that expose those failure modes before settling on safer behavior.
  evidence: `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
  confidence: high

  candidate: once the key artifact disappears, controller grounding can collapse into broad environment spelunking and risky state mutation.
  observation: KIRA `db-wal-recovery` escalates from SQLite work to overlay, mount, device, and `/app` relocation activity without surfacing a successful recovery artifact in the readable run.
  evidence: `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  confidence: high for the observed failure point; medium for treating it as family-typical.

  candidate: exploit success does not imply safe workspace behavior.
  observation: KIRA and BigAI both find working `break-filter-js-from-html` payloads, but both also introduce harness or delivery-directory hygiene problems on the way there.
  evidence: `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`, `research/sources/trajectories/BigAI/break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt`, `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
  confidence: high

  candidate: benchmark-sufficient branch deployment can under-read repo-state contamination and stale-file risks.
  observation: DeepAgents and KIRA pass the exact git-multibranch task contract, but only BigAI readable runs make branch-isolation and cleanup complaints visible enough to force repo reset and directory cleanup behavior.
  evidence: `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`, `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`, `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`, `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
  confidence: medium; weakened because the DeepAgents and KIRA risk is inferred from missing pressure, not from directly observed contamination failure.
- shared_task_comparison_matrix:
  task_1:
    task_name: `headless-terminal`
    systems_with_available_runs: `deepagents`, `terminus-kira`, `BigAI`
    pass_fail_outcome_per_system: `deepagents`: pass after verification-side implementation fix; `terminus-kira`: pass after verification-side REPL fix and cleanup; `BigAI`: pass after role-separated implementation, hang recovery, and verifier checks
    main_divergence_point: all three satisfy basic PTY-shell behavior, then diverge under REPL, cleanup, and terminal-shutdown verification pressure
    main_failure_point: `deepagents` hits daemon-thread or `tcsetattr` shutdown trouble; `terminus-kira` initially fails the REPL-write case; `BigAI` hits a hung shell experiment that requires `kill_shell_command`
    observed_behavioral_difference: `deepagents` stays in a short direct repair loop; `terminus-kira` shows stricter cleanup before completion; `BigAI` shows planner or executor or verifier handoffs and an explicit kill or re-verify cycle
    likely_mechanism_difference: KIRA and BigAI appear to gate completion more heavily on cleanup and verifier-visible behavior than the visible DeepAgents loop; BigAI also appears to use a role-separated controller
    source_backed_explanation: none in this role; the role-separated interpretation for BigAI is not source-backed here
    confidence: medium-high; weakened because mechanism explanation is behavior-first and BigAI internals remain opaque
    evidence_paths: `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`; `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`; `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
    explanation_type: behavior-only; likely mechanism difference is `trajectory-supported inference`, and the BigAI controller reading is `behavioral reconstruction`

  task_2:
    task_name: `cancel-async-tasks`
    systems_with_available_runs: `deepagents`, `terminus-kira`, `BigAI`
    pass_fail_outcome_per_system: `deepagents`: pass; `terminus-kira`: pass; `BigAI`: 3 readable runs passed
    main_divergence_point: all systems reach a working bounded-concurrency solution, but they diverge in how adversarially they test cancellation and cleanup before acceptance
    main_failure_point: no final task failure in accepted runs; the load-bearing pressure point is whether cleanup completes before controller exit and whether cancelled work can still start
    observed_behavioral_difference: `deepagents` verifies the core contract with a short probe set; `terminus-kira` repeatedly rewrites implementation and tests; `BigAI` adds the strongest verifier-side edge-case suite and repeatedly cleans the delivery directory
    likely_mechanism_difference: KIRA and especially BigAI appear to apply stronger stop-rule and cancellation-hardening discipline than the visible DeepAgents run
    source_backed_explanation: none in this role
    confidence: high for the behavioral difference; medium for the mechanism explanation because this remains behavior-first
    evidence_paths: `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`; `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`; `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`; `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`; `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
    explanation_type: behavior-only; likely mechanism difference is `trajectory-supported inference`, with BigAI role-separation claims remaining `behavioral reconstruction`

  task_3:
    task_name: `db-wal-recovery`
    systems_with_available_runs: `deepagents`, `terminus-kira`, `BigAI`
    pass_fail_outcome_per_system: `deepagents`: pass; `terminus-kira`: fail or unresolved in the readable run; `BigAI`: 3 readable runs passed
    main_divergence_point: the systems diverge sharply once the WAL file becomes the central obstacle; DeepAgents and BigAI stay artifact-local while KIRA expands into environment forensics
    main_failure_point: `terminus-kira` broadens into overlay, device, mount, and container probing and moves `/app` without surfacing a successful recovery artifact; DeepAgents and BigAI fix the WAL, verify the 11 recovered rows, and preserve clean delivery state
    observed_behavioral_difference: `deepagents` and `BigAI` remain anchored to the output contract and task artifacts; `terminus-kira` loses task-local grounding after the visible WAL dead end
    likely_mechanism_difference: DeepAgents and BigAI appear to have stronger artifact-local grounding and verification-coupled stop rules on this task than the visible KIRA run
    source_backed_explanation: none in this role
    confidence: high for the observed pass or fail split; medium-high for the mechanism explanation because the KIRA evidence is one readable failure-heavy run
    evidence_paths: `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`; `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`; `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`; `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`; `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
    explanation_type: behavior-only; likely mechanism difference is `trajectory-supported inference`

  task_4:
    task_name: `break-filter-js-from-html`
    systems_with_available_runs: `deepagents`, `terminus-kira`, `BigAI`
    pass_fail_outcome_per_system: `deepagents`: pass; `terminus-kira`: pass; `BigAI`: 2 readable runs passed
    main_divergence_point: all systems find a working bypass path, but they diverge in how much replanning and workspace cleanup they need before completion
    main_failure_point: `terminus-kira` temporarily mutates the harness path expectation inside `test_outputs.py` and later reverts it; `BigAI` either leaves extra test or backup files that must be moved out or deletes benchmark-support files and later restores them; no comparable workspace-integrity failure is visible in the DeepAgents run
    observed_behavioral_difference: `deepagents` takes the shortest task-local path; `terminus-kira` uses iterative browser or parser probing with temporary harness mutation; `BigAI` explores more hypotheses and relies on post-hoc verifier or cleanup pressure to restore workspace integrity
    likely_mechanism_difference: DeepAgents appears stronger on direct task grounding and workflow economy here, while BigAI appears stronger on post-hoc integrity recovery once workspace damage has already occurred
    source_backed_explanation: none in this role
    confidence: high
    evidence_paths: `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`; `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`; `research/sources/trajectories/BigAI/break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt`; `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
    explanation_type: behavior-only; likely mechanism difference is `trajectory-supported inference`, and any BigAI architecture reading remains `behavioral reconstruction`

  task_5:
    task_name: `git-multibranch`
    systems_with_available_runs: `deepagents`, `terminus-kira`, `BigAI`
    pass_fail_outcome_per_system: `deepagents`: pass; `terminus-kira`: pass; `BigAI`: 2 readable runs passed, including one run with stronger visible fail-then-recover hygiene pressure before acceptance
    main_divergence_point: the systems diverge after the branch-deploy path first works; BigAI continues under explicit repo-cleanliness and branch-isolation pressure while DeepAgents and KIRA do not show comparable adversarial stress in the readable runs
    main_failure_point: BigAI exposes verifier complaints about cleanliness or branch-state robustness before later resetting repos and deploy directories and re-verifying; no analogous visible failure is surfaced in the DeepAgents or KIRA readable runs
    observed_behavioral_difference: `deepagents` validates endpoint correctness and timing inside one loop; `terminus-kira` uses `git archive | tar -x` deployment and passes the benchmark contract; `BigAI` shows explicit repo hygiene, reset, and cleanup cycles before final verifier approval
    likely_mechanism_difference: BigAI appears stronger under repo-state pressure because verifier-driven hygiene and reset behavior are much more visible; DeepAgents and KIRA may be benchmark-sufficient here without visibly stress-testing stale-file and branch-isolation hazards
    source_backed_explanation: none in this role
    confidence: high for the observed divergence; medium for the mechanism explanation because this is still behavior-first and run-conditioned
    evidence_paths: `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`; `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`; `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`; `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
    explanation_type: behavior-only; likely mechanism difference is `trajectory-supported inference`, with the BigAI orchestration reading partly `behavioral reconstruction`
- cross_run_priority_findings:
  finding_1:
    task_name: `db-wal-recovery`
    systems_compared: `deepagents` vs `terminus-kira`
    pass_fail_outcome_per_system: `deepagents`: pass; `terminus-kira`: fail or unresolved in the readable run
    divergence_point: after the WAL path becomes nontrivial, DeepAgents stays with database bytes and output-schema verification while KIRA broadens into environment-level forensics
    failure_point: KIRA never surfaces a visible successful `recovered.json` or final 11-row verification in the readable run
    observed_behavioral_difference: DeepAgents remains task-local and verifier-grounded; KIRA loses grounding and scope discipline
    likely_mechanism_hypothesis: DeepAgents shows stronger artifact-local grounding and stop discipline on this task
    source_backed_mechanism_explanation: none in this role
    confidence: high for the success-vs-failure split; medium-high for the mechanism explanation
    evidence_paths: `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`; `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
    explanation_type: behavior-only; likely mechanism explanation is `trajectory-supported inference`

  finding_2:
    task_name: `db-wal-recovery`
    systems_compared: `BigAI` vs `terminus-kira`
    pass_fail_outcome_per_system: `BigAI`: 3 readable runs passed; `terminus-kira`: fail or unresolved in the readable run
    divergence_point: BigAI readable runs stay fixed on WAL repair, JSON output, and clean delivery-state restoration while KIRA broadens into environment forensics
    failure_point: KIRA shows no visible successful recovery artifact; BigAI verifier reports repeatedly confirm 11 recovered rows and clean delivery state
    observed_behavioral_difference: BigAI keeps reopening or checking the concrete output contract under verifier pressure instead of broadening the task scope
    likely_mechanism_hypothesis: BigAI appears to have stronger verifier-coupled grounding and recovery on this task than the visible KIRA run
    source_backed_mechanism_explanation: none in this role; any BigAI controller explanation remains `behavioral reconstruction`
    confidence: high for the success-vs-failure split; medium for the mechanism explanation
    evidence_paths: `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`; `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`; `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`; `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
    explanation_type: behavior-only; likely mechanism explanation is `trajectory-supported inference`, with BigAI internals remaining `behavioral reconstruction`
- cross_family_comparisons:
  comparison: DeepAgents and Terminus-KIRA both validate that a direct grounded shell loop is a genuine family in this domain, while BigAI validates that a role-separated planner or executor or verifier regime is also real in the same mechanism area.
  evidence: `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`, `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`, `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
  confidence: high

  comparison: the strongest visible evidence for `repo-state-safe action execution` comes from BigAI pressure-tested runs, but that may reflect stronger verifier pressure rather than a universally stronger family mechanism.
  evidence: `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`, `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`, `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`, `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
  confidence: medium

  comparison: the clearest cross-system failure contrast is not in cancellation or git deployment, where all readable systems pass, but in `db-wal-recovery`, where artifact-local grounding visibly separates successful runs from the failure-heavy KIRA run.
  evidence: `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`, `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`, `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`, `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`, `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
  confidence: high
- contradiction_notes:
  contradiction: terminal realism looks cross-family in behavior, but the visible control styles are not one mechanism story.
  observation: DeepAgents and KIRA expose direct PTY or shell loops, while BigAI exposes role-separated planner or verifier behavior without visible source.
  implication: execution-control and terminal-grounding look like real cross-family mechanism areas, but not as one unified architecture.
  evidence: `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`, `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`, `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
  confidence: high

  contradiction: benchmark pass and repo-state safety are not visibly equivalent.
  observation: DeepAgents and KIRA pass `git-multibranch` directly, while BigAI only looks robust after verifier-visible hygiene or reset cycles.
  implication: repo-state-safe execution needs a stronger card than “the branch deploy task passed.”
  evidence: `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`, `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`, `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`, `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
  confidence: medium

  contradiction: explicit interrupt support does not guarantee broader task recovery.
  observation: KIRA proves it can send `C-c`, but `db-wal-recovery` still spirals after the key artifact disappears.
  implication: interruptibility is necessary but not sufficient for grounded recovery.
  evidence: `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`, `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  confidence: medium

  contradiction: finding a working exploit and preserving verifier-visible workspace integrity can point in opposite directions.
  observation: BigAI and KIRA both succeed on `break-filter-js-from-html`, but both also create workspace or harness hygiene problems that must be repaired.
  implication: mechanism cards need a distinct restore or hygiene surface, not only a “found working answer” surface.
  evidence: `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`, `research/sources/trajectories/BigAI/break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt`, `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
  confidence: high
- confidence_notes:
  high-confidence zone: readable-run coverage for the five in-scope shared task families is exhaustive; every readable `*-traj.txt` under those directories was inspected.
  high-confidence zone: `db-wal-recovery` now has readable coverage across all three systems, and the KIRA fail or unresolved outcome stands out against DeepAgents and BigAI readable passes.
  medium-confidence zone: archive-only in-scope runs were inventoried but not unpacked, so this is still partial wave-scope coverage.
  medium-confidence zone: BigAI mechanism explanations remain `behavioral reconstruction` without mirrored source.
  medium-confidence zone: KIRA family-level judgments remain weaker where only one readable run exists for the visible failure mode.
- open_questions:
  do the archive-only BigAI variants reinforce or weaken the current cross-run story, especially for `db-wal-recovery` and `git-multibranch`?
  does same-wave source analysis confirm that BigAI’s stronger repo reset and verifier loops are framework-level mechanisms rather than task-conditioned policy?
  does KIRA source expose hidden cleanup or grounding safeguards that the failure-heavy readable `db-wal-recovery` run never reached?
  how much of the repeated verifier gating is harness policy versus benchmark-specific completion-contract pressure?
- next_hand_off_target: tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/contradiction_analyst.md
