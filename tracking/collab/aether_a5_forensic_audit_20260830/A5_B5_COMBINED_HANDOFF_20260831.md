# A5 rerun + B5 terminal handoff

Date: 2026-08-31
Owner: `/root`
Status: **both authorised runs terminal; evidence packaged; no retries; no promotion**

This is the combined handoff for the one authorised A5 rerun and the one authorised B5 run. It is a result/evidence handoff, not a claim that the model or harness has passed the benchmark. The run authorization explicitly permitted normal Azure charges, accepted an unmeasured provider cost (`cost_usd: null`), and forbade retries. No additional provider calls, benchmark retries, source substitutions, merges, or promotions were made.

## 1. Authorization and execution boundary

- Authorization receipt: `launch_evidence_20260831/authorized_exception-20260831T124957Z/COST_EXCEPTION_AUTHORIZATION.json`.
- Scope: exactly one A5 run (five rows) and one B5 run (five rows), one first-submit attempt per row, SDK/benchmark retries `0`.
- Model/treatment: protected GPT-5.6 Luna; the sealed treatment used low Solver effort, `previous_response` Solver continuity, fresh independent Verifier, `minimal_v1` context, `control_8k` attention, and native compaction off.
- A5 and B5 were frozen at their respective sealed source identities. No implementation change occurred between the two benchmark runs.
- This package records observed terminal state separately from reward validity, provider validity, and model quality.

## 2. A5 rerun (recurrence diagnostic)

### Sealed identity

- Source commit: `36e7b60190f18bf9c3c929cac2f98813f8ee2f04`.
- Source tree: `464a71fc3cbf6d70e6a52a3753453f13d9ef73fd`.
- Runtime manifest file SHA: `d1cbc527078c67bd6c4588220cd98a5609d9d3385298568698df7a01cf97754f`.
- A5 sentinel SHA: `201d5309f42f3335e4e779790ab6fbfb5fa7c502d8aaf9cd5e8382b2fbcae612` (embedded); remote sentinel identity SHA recorded as `1bc0f5e73ae6bea818c812e03079b2aed72d8013dce1474e3ca36907648222fb`.
- Evidence manifest SHA: `42e433cc22f355e8963cc900f7611f664194e5c34aad0938af8cff1f8c9fbb9a`.
- Evidence root (retained locally): `launch_evidence_20260831/authorized_exception-20260831T124957Z/a5/`.

### Terminal rows

The A5 sentinel reports `A5_ALL_ROWS_TERMINAL`, five rows, and no retries. Four rows completed with reward `0.0`; `bn-fit-modify` terminated as an invalid environment row and is not a capability score. The retained row manifests are the authority for each status.

| row | run id | terminal status | reward/cost interpretation |
|---|---|---|---|
| `bn-fit-modify` | `a5-bn-fit-modify-20260831-01` | `TERMINAL_INVALID_ENVIRONMENT` | invalid measurement; no capability reward |
| `circuit-fibsqrt` | `a5-circuit-fibsqrt-20260831-01` | `TERMINAL_COMPLETED_REWARD_0` | reward `0.0`; runner reports `cost_usd: 0.0` |
| `data-anonymization` | `a5-data-anonymization-20260831-01` | `TERMINAL_COMPLETED_REWARD_0` | reward `0.0`; runner reports `cost_usd: 0.0` |
| `polyglot-rust-c` | `a5-polyglot-rust-c-20260831-01` | `TERMINAL_COMPLETED_REWARD_0` | reward `0.0`; runner reports `cost_usd: 0.0` |
| `session-window-debug` | `a5-session-window-debug-20260831-01` | `TERMINAL_COMPLETED_REWARD_0` | reward `0.0`; runner reports `cost_usd: 0.0` |

The A5 run is therefore terminal, but it is not a passing or promotion result. The audit’s causal findings and limitations remain in `A5_FORENSIC_AUDIT.md`, `MICROSCOPIC_INFORMATION_FLOW_AUDIT.md`, and `ADVERSARIAL_RESOLUTION.md`. In particular, the evidence supports direct source-visible defects and harness information-loss findings; it does not prove a universal Luna capability limit, and the exact child-level cause of the privilege-drop/retraction report remains bounded or unclear where child evidence is absent.

## 3. B5 run (forward five-task board)

### Sealed identity and trigger

- Candidate/source commit: `a24b1487ac5e65c0b6e352337bbff4028d8f10db`.
- Source tree: `03f15411db94e039d729e7552b66a27939530711`.
- Runtime manifest SHA: `d1cbc527078c67bd6c4588220cd98a5609d9d3385298568698df7a01cf97754f`.
- Candidate config SHA: `c9cc5d721577d9c65577fc3328f930ccacdd97e123b6001c88af04a9899dfcc4`.
- Trigger ID: `844d29a01a8f9426c14c3e00dd5f70c8bb75ae30f8744236404403d357c8214a`.
- Trigger plan SHA: `d18e3b0be5cca6f8c1cbd6a864a1309ca823509c1bf30c0fc177bfb52373fce6`.
- Trigger source scheduler SHA: `c8efd3f7517d97a6a0e58f8f469d4da839b20d18a3b073d90be2eae1bb0dee40`; trigger script SHA: `bacdee0c98aa6fbc34ee22a5863877bb762a842374091b3b678628567fbaeab0`.
- Trigger state file SHA (local snapshot and remote): `3042d58d6b9563b452429a30a3de45d4eeab597a9eb7119166223a2f2b625db0`.
- `LAUNCH_RESULT.json` SHA: `95cccd01966e4a4814057ad06fae6dbc2a4b7c387c94471446e91fe196b0405a`.
- `TRIGGER_IDENTITY.json` SHA: `5e65d8c2a609019e8a8da7c8e1425d387be720987569628f05da61f06e3a8561`.
- `LAUNCH_PLAN.json` SHA: `59c5e6670ef75d24f1e0dc2562bd6e939a6b319417cf754564f6bf1ecae06130`.
- Original remote roots: `/home/azureuser/a5_b5_parallel_20260831/trigger-evidence`, `/home/azureuser/a5_b5_parallel_20260831/trigger.state.json`, `/home/azureuser/a5_b5_parallel_20260831/jobs`, and `/home/azureuser/a5_b5_parallel_20260831/leases` on `aether-solver-vm` (`20.9.17.92`).
- Local immutable snapshot: `launch_evidence_20260831/authorized_exception-20260831T124957Z/b5_parallel_requalification/remote_snapshot_20260831/`; key-file hashes were rechecked against the remote host.

### Terminal state and rows

Independent SSH inspection at `2026-08-31T16:56:04Z` found controller PID `68698` absent, trigger state `LAUNCHED_TERMINAL`, five task return codes `0`, and all five leases present with `RELEASED` state. There was no retry or second trigger. The task-level runner results all report reward `0.0` in their `aether-next__adhoc` metric; that is a failed forward-board outcome, not a pass.

| task | first-submit run id | task-result SHA-256 | top-level result SHA-256 | observed classifier / validity |
|---|---|---|---|---|
| `wal-recovery-ordering` | `first-submit:5713fec83499919f08ad934b714402b153640d02f9d0e9dbfa720a704b02df44` | `fb1301022cc65bd30c2b6e000d8985db3590df227169d030e9d9ef7c23aed428` | `b6392a39d6279b58091d3b14bbaf7df26168e2dc6e8d5f3a9d4c878b28f7c75b` | reward `0.0`; terminal row, classifier `none` |
| `cad-model` | `first-submit:3493ddb2f288202e699779273842192f41d26c1454a18a5408b7dad6aa64552a` | `9688eccdf40884ff0c040db0b7d72a32fe1b0c14e27e7ffb29bac76c51f5caef` | `4fff3609aa3322b4193d11f92d5cb2ac39fb73fa2a7cdcdaaf0c8b75ee7b042f` | reward `0.0`; provider/verifier protocol failure observed |
| `dna-assembly` | `first-submit:c7399df7fad8dbb56e562da6a853a84517deb08f05c6d8a0ddcdc826a6ffea26` | `283407c63ff2ea00a6ee1221397fa57341c88f997ff0ca3c7e16d0612ead8e80` | `e3687aeaa27303de0f6623e2212ca75bda11e501a25460737a06a1c8c4c5dc19` | reward `0.0`; provider/verifier protocol failure observed |
| `llm-inference-batching-scheduler` | `first-submit:9f0c3fa8288dc95c985ed454aeedacda35455da561d5aa49a13a947fd1cf9c47` | `8c34845ad45451b15b76b4666dd8da0668d8dae722ac5f9b14f1e38ddcb45478` | `22e31aa5f7523ff153745f57822aed59659180c84197c63477c09069ce3ec282` | reward `0.0`; provider-failure classifier observed |
| `make-mips-interpreter` | `first-submit:8953c89f7e4f0bfc58ec07b70a5147fa7bec8fb99c5741f65597e4d6dd4aa817` | `db5b9d918617de9658a344a87e3e15870d4e182d88530efebea1eadf82937695` | `efe6edaff8715c9095ed21487ae621edd2c6ea142d8a64a393853521e7fd86b1` | reward `0.0`; harness-context/solver-stalemate classifier observed |

The B5 top-level result files show `cost_usd: 0.0`, while the authorized policy explicitly accepts unmeasured cost and the current Azure principal cannot read authoritative billing data. Treat monetary attribution as **unmeasured**, not as evidence that the run was free. Token/cache telemetry and full per-task trajectories are retained in the local snapshot; reward, provider, Verifier, and grader status must be read from each task’s result/trajectory rather than inferred from return code.

The B5 scheduler used two resource-aware waves (WAL + CAD, then DNA + LLM + MIPS) under the observed carrier capacity. This proves the trigger’s chosen execution, not that arbitrary three-way parallelism is safe for every future carrier.

## 4. Process, lease, VM, and evidence custody

- The B5 controller was absent at terminal inspection; all five leases were `RELEASED`; no A5/B5 retry process was started.
- Remote key artifacts were copied to the local snapshot and SHA-256 compared with the remote host. The snapshot is 15 MB for the selected job/trigger evidence; the remote job tree remains the complete source of record.
- Azure CLI read-only VM inspection failed with `AuthorizationFailed` for `Microsoft.Compute/virtualMachines/read`; VM power/deallocation could not be independently established by the current principal. This is an environment/permission limitation, not a benchmark result.
- No claim is made that the VM is deallocated. The next operator with Azure Compute permission should perform a read-only state check and deallocate only after verifying no authorized job remains.
- No process/container/server/agent watcher remains intentionally active from this closeout; the Luna watcher exited after terminal retrieval.

## 5. Reusable launch bundle implementation

The benchmark-neutral launch bundle is integrated on the root branch `fix/postrun-p0-harness-fixes`:

- `ca4995e30 Add benchmark-neutral sealed launch bundle`
- `9eb2d0e03 Harden benchmark-neutral launch bundle integrity and custody`

Primary files: `tools/bench_launch.py`, `tools/bench_run_spec.schema.json`, `examples/bench_run_spec.json`, `docs/bench_launch.md`, and `tests/test_bench_launch.py`.

Fresh root focused validation: `PYTHONPATH=. python3.11 -m pytest -q tests/test_bench_launch.py` -> **29 passed**; `py_compile`, schema/example parsing, and `git diff --check` passed. The bundled `codex review` executable was unavailable (`.../vendor/aarch64-apple-darwin/codex/codex ENOENT`), so root independently reconciled the latest hardening and retains the adversarial reviewer’s one bounded limitation: detached hostile children are cleaned up on a best-effort process-table/settle-window basis, not a certifying OS sandbox. The bundle is a safe, fail-closed dispatch primitive; it is not by itself a benchmark certification.

The root checkout contains unrelated user modifications and untracked audit/eval material. They were preserved; no reset, cleanup, merge, or promotion was performed.

## 6. Required interpretation and next owner action

1. Treat A5 as a terminal recurrence diagnostic with four completed reward-0 rows and one invalid environment row; do not average it as a clean five-row capability score.
2. Treat B5 as a terminal five-row board with all return codes zero but all observed rewards zero and several protocol/context failure classifications; it is not a quality pass or promotion gate.
3. Preserve the copied evidence and original remote paths. Do not rerun either run under this authorization.
4. If continuing engineering, use the integrated generic launch bundle and the existing A5 implementation/fix plan as the source for a new, separately governed goal. Any new provider run, changed task family, merge, or promotion needs fresh authority.
5. Resolve VM lifecycle with an Azure-authorized operator and route the unmeasured billing status honestly.

## 7. Raw ledger and delivery receipts

Raw historian inputs are persisted at:

- `tracking/ledger/inbox/2026-08-31T16-56-11Z-b5-closeout.md` (Luna watcher closeout).
- `tracking/ledger/inbox/20260831T_root_a5_b5_closeout.raw.md` (this root consolidation).
- Candidate launcher implementation/review inputs under the isolated bundle worktree’s `tracking/ledger/inbox/`.

The prescribed recorder `tracking/ledger/tools/record_update.py` is absent in this checkout; no canonical ledger files were edited.

This handoff was sent to the requested destination task `019f4c70-5d06-7033-a995-d447bf06067d` with `mcp__codex_app__send_message_to_thread` after this file and the raw ledger consolidation were persisted.

Delivery receipt: tool returned `isError: false` with `{"threadId":"019f4c70-5d06-7033-a995-d447bf06067d"}`.
