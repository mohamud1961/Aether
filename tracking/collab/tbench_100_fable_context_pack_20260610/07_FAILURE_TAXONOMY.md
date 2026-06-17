# 07 — Failure Taxonomy

Ranked roughly by measured impact (highest first), drawing on `06`'s
evidence and `04`'s decision history. For each: definition, evidence,
example paths, current mitigation, status, TB impact, generic fix options,
benchification risk.

---

## 1. Filesystem / cwd / path confusion

- **Definition**: Agent operates on the wrong working directory, wrong
  root, or matches the wrong target file (decoys, similar names, relative
  vs. absolute paths).
- **Evidence**: 0/6 on the filesystem family (2026-05-30 diagnostic, `06`#3)
  — every row failed on "wrong cwd/root and wrong target-file pattern
  matching."
- **Example paths**: `tracking/collab/eval_suite_v1_baseline/certified_runs/.../result_rows.jsonl`
  (filesystem family rows), `final_harness_eval_suite/task_packs/hard/`
  (`fhard_03_filesystem_decoy_patch`, `fhard_08_original_noisy_open_workflow`).
- **Current mitigation**: None implemented. Proposed:
  `filesystem_cwd_path_normalization_wrapper_01` (backlog,
  `vm-pulled:tracking/collab/variant_hypothesis_backlog.md`) — normalize
  cwd/path resolution before filesystem actions. Also relevant:
  `candidate_plus_app_workspace_path_normalizer_01`,
  `v04_ex_02_cwd_workdir_invariant_propagation_guard`,
  `v04_cb_01_decoy_resistant_target_selection` (Goal 1 closeout
  recommendations, `04` Phase 4).
- **Status**: **OPEN** — worst-measured family, zero implemented fixes.
- **TB impact**: Very high — TB2.0 tasks routinely involve multi-directory
  repos, decoy files, and relative-path traps.
- **Generic fix options**: a thin path-normalization wrapper around
  filesystem-touching tool calls (resolve relative to a canonical workspace
  root, validate target existence/uniqueness before acting); a "workspace
  map" injected into context at orientation time.
- **Benchification risk**: LOW if implemented as a generic
  cwd/path-normalization layer; HIGH if implemented as
  task-specific path lookup tables.

---

## 2. Service readiness / process identity confusion

- **Definition**: Agent starts a service/process but cannot correctly prove
  it is ready (wrong process identity check, missing readiness receipt,
  premature "done" claim about a service).
- **Evidence**: 0/3 on the service-readiness family (2026-05-30 diagnostic)
  — every row failed on "wrong process identity + missing readiness proof."
- **Example paths**: `tracking/collab/eval_suite_v1_repair_runs/20260526T165436Z_service_process_readiness_rerun/result_rows.jsonl`,
  `final_harness_eval_suite/task_packs/hard/fhard_02_service_orchestration_flagship`.
- **Current mitigation**: None implemented. Proposed:
  `service_contract_first_receipt_closure_01` (backlog, flagged "**strongest
  next service-family bet**" as of 2026-05-26) — read `service_config.json`
  first, satisfy the visible `trace_contract` literally, emit a canonical
  `readiness_receipt.json`, normalize `process_identity` to
  `python3 service_runtime.py`. Predicted **0/3 → 3/3**.
- **Status**: **OPEN** — second-worst-measured family, one concrete,
  evidence-backed, predicted-uplift fix sitting unimplemented for 2 weeks.
- **TB impact**: High — many TB2.0 tasks involve starting a server/daemon
  and verifying it's actually serving (port-open-but-protocol-broken,
  below, is closely related).
- **Generic fix options**: `service_contract_first_receipt_closure_01` as
  designed; more generally, a `kernel_services.py`-driven
  "read-config → satisfy-contract → emit-receipt → verify-from-outside"
  loop usable across any service-style task.
- **Benchification risk**: LOW if the receipt format and process-identity
  normalization are generic; the proposed normalization to
  `python3 service_runtime.py` should be checked it isn't hardcoded to one
  task's filename — if it is, generalize before adoption.

---

## 3. Service readiness hallucination / port-open-but-protocol-broken

- **Definition**: Agent (or harness) believes a service is ready because a
  port is open or a process exists, but the actual protocol/application
  layer is broken or not yet initialized.
- **Evidence**: Implicit in failure class #2 (0/3) and in
  `ungoverned_model_claim` discussions throughout `04`. Not separately
  scored, but named explicitly in this packet's required taxonomy and
  closely tied to GOVERNED_STATUSES' `service_not_ready`.
- **Current mitigation**: `GOVERNED_STATUSES` includes `service_not_ready`
  as a distinct outcome (kernel_gates.py) — the vocabulary exists, but
  whether the kernel actually probes protocol-level readiness (vs.
  port-level) is unverified.
- **Status**: **PARTIALLY ADDRESSED at vocabulary level, OPEN at mechanism
  level** (folds into #2).
- **TB impact**: High, same as #2.
- **Generic fix options**: protocol-level health checks (HTTP GET, not just
  TCP connect) as part of the readiness receipt in #2.
- **Benchification risk**: LOW.

---

## 4. Context / evidence-carry-forward / reduction failures

- **Definition**: Agent loses or fails to retrieve relevant prior evidence,
  retrieves the wrong field, or context becomes stale after a mutation.
- **Evidence**: 2/7 on context/reduction family (2026-05-30 diagnostic) —
  "evidence carry-forward, relevant retrieval, wrong field, stale state
  after mutation."
- **Example paths**: `tracking/collab/eval_suite_v1_baseline/certified_runs/.../result_rows.jsonl`
  (context family rows), `runner/kernel_context_pack.py`,
  `runner/kernel_compaction.py`.
- **Current mitigation**: Phase 6 (2026-06-05) fixed the most egregious
  instance — `render_context_pack`'s naive `[:6000]` character-slicing —
  with adaptive compaction using evidence-trail/receipt/service/artifact
  projections. **This fix is unscored** against the context family.
- **Status**: **PARTIALLY ADDRESSED (code-level), UNVERIFIED (eval-level)**.
- **TB impact**: High for any multi-step task requiring the agent to
  remember earlier findings (file contents, command outputs, prior errors).
- **Generic fix options**: rerun the 2026-05-30 context family against the
  Phase 6 context-pack fix as the highest-value "is our recent work actually
  helping" check; backlog candidates `stateful_compaction_external_context_01`,
  `evidence_state_capsule_context_v1`, `verified_work_pocket_redesign`,
  `continuous_context_compaction_01` (Claude/Codex-style rolling
  compaction) remain `never_evaluated_backlog`.
- **Benchification risk**: LOW-MEDIUM — context/compaction strategies are
  generally generalizable, but watch for compaction heuristics tuned to
  this eval suite's specific task shapes.

---

## 5. Environment / toolchain / dependency confusion

- **Definition**: Agent fails due to stale documentation references, wrong
  canonical-runner discovery, or wrong interpreter/toolchain invocation
  (e.g. `python` vs `python3`, wrong venv).
- **Evidence**: 4/7 on environment/toolchain family (2026-05-30 diagnostic).
- **Current mitigation**: None implemented beyond general harness
  improvements. Proposed: `dependency_runner_resolution_contract_01`
  (backlog) — normalize interpreter/toolchain discovery.
- **Status**: **OPEN**, moderate priority (4/7 is mid-pack).
- **TB impact**: Medium-high — frequent in real repos.
- **Generic fix options**: `dependency_runner_resolution_contract_01` as
  designed — a generic "discover the right interpreter/build tool for this
  repo" step at orientation time.
- **Benchification risk**: LOW.

---

## 6. Tool-contract / schema mismatch (incl. ignored results, no-call traps)

- **Definition**: Wrong argument shape/value for a tool call, tool result
  ignored or not attributed correctly, model fails to call a required tool
  or calls one prematurely (no-call traps), stale/superseded result IDs
  retained.
- **Evidence**: tooling baseline 4/7 → 7/7 with combined guard (2026-05-30),
  but combined guard has a **sentinel regression (0/1)** on
  `ctc_semantics_001_multi_required_order` (2026-05-17 tournament, `06`#1).
  Separately, `tool_result_attribution` family scored 0/2 target, 0/1
  sentinel across all 4 tested variants (2026-05-18, `06`#2).
- **Example paths**: `blocks/tools/result_attribution_guard_common.py`,
  `tracking/collab/first_result_attribution_mechanism_tournament/`,
  `vm-pulled:tracking/collab/autonomous_loop/single_family_winner_discovery_gate/tool_result_attribution/`.
- **Current mitigation**: "Combined Guard V1.5" exists but is
  **hardcoded** (injects `lookup_customer_order: include_history=True`
  specifically) and **sentinel-regressed** — should not be re-promoted
  as-is.
- **Status**: **PARTIALLY ADDRESSED for the narrow tooling-baseline family
  (with caveats), OPEN/REGRESSED for the broader tool_result_attribution
  family** (0/2 across all tested variants as of 2026-05-18 — worse than
  filesystem in some sense, since multiple variants were tried and all
  failed).
- **TB impact**: High — TB2.0 tasks frequently chain multiple tool calls
  whose results must be correctly attributed/used.
- **Generic fix options**: Goal 1's recommended next candidates —
  `tool_call_contract_classifier`, `permission_runtime_attribution_split` —
  plus fixing hidden-truth leakage/solver isolation in the eval itself
  (the eval may be partially broken, not just the harness — this needs
  diagnosis before more mechanism attempts). Backlog's
  `programmable_tool_calling_plus_bash_01` (typed action DSL: `repo_search`,
  `file_read`, `run_command`, `run_verifier`, `inspect_artifact`,
  `start_service`, `check_service`, compiled to bounded bash with normalized
  receipts, raw_bash fallback preserved) is the most structural proposed fix
  and is `never_evaluated_backlog`.
- **Benchification risk**: MEDIUM — guard mechanisms here have repeatedly
  trended toward hardcoded, tool-name-specific repairs (Combined Guard
  V1.5). Any new mechanism must be checked for genericity (does it work for
  ANY tool/argument, not just the eval's specific tools).

---

## 7. Finalization-truth bug / `ungoverned_model_claim`

- **Definition**: Model declares a task complete (`governed_pass`-style
  claim) without the harness verifying that declared success criteria were
  actually met.
- **Evidence**: This is the central motivating failure class for the entire
  Active Evidence Kernel + Layer-2 audit lineage (Phases 1 and 6, `04`).
  Phase 6's adversarial review found 3 of its 4 fixes were directly about
  this: dead Layer-2 auditor, missing success-contract prompt injection,
  finalization gates not blocking on `success_contract_missing`.
- **Example paths**: `runner/kernel_gates.py` (`GOVERNED_STATUSES`),
  `runner/kernel_layer2_audit.py`, `runner/kernel_success_contract.py`,
  `tracking/collab/model_led_substrate_v1/reviews/adversarial_review_01.md`.
- **Current mitigation**: Code-level fix complete (2026-06-05) — Layer-2
  audit wired in, success-contract injected, gates block on missing
  contracts. **Decision made to bypass the finalization loop in legacy
  routes** (two finalization code paths now exist: legacy bypass + model-led
  Layer-2 loop).
- **Status**: **PARTIALLY ADDRESSED at code level, UNVERIFIED at eval
  level** — and `agent.py` (the actual current runner entrypoint, per `05`)
  imports `evidence_kernel.py`, not `active_evidence_kernel.py`, so it's
  unclear whether this fix is even reachable from the current default
  runner without further wiring.
- **TB impact**: Very high — a harness that can't trust its own "done"
  signal cannot reliably stop at the right time, which directly caps
  pass-rate (false positives) and efficiency (false negatives → wasted
  steps).
- **Generic fix options**: the implemented Layer-2 audit + success contract
  approach (verify, eval-score it); alternatively/additionally, Stop-Hook
  style completion vetoes (option H, `03`) as a simpler complementary
  mechanism.
- **Benchification risk**: MEDIUM — `_clean_hidden_refs()` in
  `kernel_layer2_audit.py` (strips `expected`/`hidden`/`secret`/`grader`/
  `ground_truth` keys) is a *good* anti-leakage pattern, but the overall
  audit mechanism must be checked that it doesn't end up effectively
  re-deriving the hidden grader's logic (verifier-as-oracle risk, `09`).

---

## 8. Architecture churn without scored deltas (process failure, not code failure)

- **Definition**: Building a new architecture/mechanism before the previous
  one is scored, repeatedly, such that no architecture accumulates
  comparative evidence.
- **Evidence**: `04`'s entire Phase 3→7 sequence — Combined Guard V1.5
  (sentinel-regressed but called "perfect"), `winning_harness_v1` (HOLD,
  never rerun), model-led substrate v1 (built next, unscored), MLPCP v3 (pulled and paused, unscored end-to-end).
- **Current mitigation**: AGENTS.md's Experiment Discipline rules exist and
  are well-written; they are simply not being followed in sequence.
- **Status**: **OPEN** — this is arguably the highest-leverage "fix" of all,
  since it's process not code.
- **TB impact**: Indirect but severe — every week spent building unscored
  architecture is a week not spent closing #1/#2/#4/#6 (the
  evidence-backed, high-impact, unimplemented fixes).
- **Generic fix options**: Fable's execution plan (`12`) should explicitly
  sequence "score what exists" before "build what's new," and should
  resolve the Docker/eval-loop blocker (#9) as step 0.
- **Benchification risk**: N/A (process issue).

---

## 9. Local Docker unavailability invalidating certified runs

- **Definition**: Most "certified" run attempts on the local Mac dev
  environment fail with `INVALID` (not `FAIL`) because the Docker daemon
  isn't running/available, while the Azure VM Docker backend is confirmed
  to work.
- **Evidence**: `winning_harness_v1`'s 62/62 INVALID rows (`06`#4); the
  2026-05-18 authority audit found mislabeled `azure_vm_docker` rows that
  actually ran on a failed local socket (`06`#2); `local_iteration_loop_2026-06-04`'s
  scored output is missing entirely (possibly related, `06`#5).
- **Current mitigation**: Azure VM Docker backend (`harnesseng-dev`) is
  proven to work (2026-05-17 tournament). AGENTS.md mandates
  `scripts/deallocate_harnesseng_vm.sh` and
  `scripts/configure_harnesseng_vm_autoshutdown.sh` for its lifecycle —
  **both scripts are missing from the repo** (`02`, `gap_report.md`).
- **Status**: **OPEN** — this is the single highest-leverage infrastructure
  fix; resolving it would let `winning_harness_v1` (item 4, `06`) be scored
  in hours, not weeks.
- **TB impact**: Blocks ALL certified evidence generation locally.
- **Generic fix options**: (a) recreate the missing VM lifecycle scripts;
  (b) establish a default "score on Azure VM Docker" workflow for any
  candidate harness change; (c) investigate whether local Docker can be
  made to work (Colima/Docker Desktop on the Mac) as a faster inner loop,
  with Azure VM as the certified outer loop.
- **Benchification risk**: N/A (infrastructure).

---

## 10. Repeated inspection/repair loops, excessive caution/forcing, step/token efficiency

- **Definition**: Agent gets stuck re-inspecting the same state repeatedly
  without making progress (loops), or alternates between excessive caution
  (refusing to act) and excessive forcing (brute-force retries).
- **Evidence**: Indirect — Antigravity's 2026-05-30 trace analysis
  (`tracking/terminalbench_100_theoretical_harness_specification.md`)
  characterizes BigAI traces as "chatty" (~75 steps/run) vs. Vix's ~22
  steps, attributing efficiency to static system prompts + session
  forking + VFS minification ("Stem Agents"). Not independently scored for
  Aether.
- **Current mitigation**: `kernel_recovery.py`'s "bounded recovery policy"
  and `kernel_tpm_pacer.py` exist but their effect on step/token efficiency
  is unmeasured.
- **Status**: **UNKNOWN** — no Aether-specific measurement of step/token
  efficiency exists; the $0.19/run and <12-step "Zero-Abstraction" claims
  are unvalidated predictions, and the one related lean run regressed.
- **TB impact**: Affects cost and step-budget exhaustion (TB2.0 has step/
  time limits), but is secondary to correctness gaps #1/#2/#4/#6.
- **Generic fix options**: "Stem Agents" pattern (static prompts + session
  forking) is worth a small, eval-gated diagnostic; not a priority over
  correctness gaps.
- **Benchification risk**: LOW, but watch for "VFS minification"
  (comment-stripping) interacting badly with tasks where comments are
  meaningful.

---

## 11. Unsupported finalization / weak compile-only proof / fake-stub artifacts / no-artifact

- **Definition**: A family of related issues where the agent (or an eval's
  grader) accepts "it compiles" or "a file with the right name exists" as
  proof of correctness, without checking semantic content.
- **Evidence**: Not independently scored as a distinct family in this
  packet's evidence base, but implied by the "non-discriminating"
  `terminalbench_verifier_repair` eval (`06`#2) — both routes passed all
  rows, suggesting the eval's verifier may not be strict enough to catch
  weak/fake artifacts.
- **Current mitigation**: `kernel_artifacts.py`'s artifact registry +
  `kernel_gates.py`'s `artifact_gate_failed` status provide vocabulary;
  `phase65_measurement_grading.py`'s approach of parsing the official task's
  own `tests/test_outputs.py` for `SOLUTION` is a good pattern for truthful
  grading.
- **Status**: **UNKNOWN/PARTIAL** — the `terminalbench_verifier_repair`
  eval needs to be made more discriminating (Goal 1 recommendation,
  unexecuted) before this can be scored.
- **TB impact**: High in principle — TB2.0's hidden verifiers should catch
  this, but a harness that doesn't self-check leaves it entirely to the
  hidden verifier (no early feedback loop for the model).
- **Generic fix options**: strengthen `terminalbench_verifier_repair` eval
  pressure (Goal 1 recommendation); ensure `artifact_gate_failed` actually
  fires on semantic-content checks, not just existence checks.
- **Benchification risk**: MEDIUM — "semantic content checks" must be
  generic (e.g., "does the output match the schema and pass any provided
  test"), not derived from the specific hidden grader's expected values.

---

## 12. Hidden/eval leakage (tool_result_attribution family)

- **Definition**: An eval's own fixture may leak hidden-truth information
  to the solver, or fail to isolate the solver from grader internals,
  producing misleading 0/2 results that reflect an eval bug rather than a
  harness gap.
- **Evidence**: Goal 1 closeout's recommendation for
  `tool_result_attribution`: "repair hidden-truth leakage/solver isolation"
  before testing new mechanisms — implies the eval itself may be
  compromised.
- **Status**: **UNKNOWN** — diagnosis not completed.
- **TB impact**: If the eval is broken, all 0/2 results in this family
  (`06`#2, `07`#6) may be uninformative — this should be resolved before
  investing more mechanism effort in `tool_result_attribution`.
- **Generic fix options**: a Trace Diff Workbench pass (per AGENTS.md) on
  this eval's fixtures specifically.
- **Benchification risk**: N/A (eval-quality issue, but closely tied to
  `09`'s "official task exposure" risk if the leakage involves real TB
  task internals).

---

## 13. Stale cockpit/context, decision-history fragmentation (process)

- **Definition**: The canonical ledger is 2+ months stale; 27 raw handoffs
  sit unprocessed; `AGENTS.md` references files (`variant_hypothesis_backlog.md`,
  `docs/current_surface_map.md`, `docs/deprecation_map.md`) that don't exist
  on `master`; `tracking/collab/` has duplicate/divergent content between
  `master` and `vm-pulled`.
- **Evidence**: `02`, `gap_report.md`.
- **Status**: **OPEN**.
- **TB impact**: Indirect — increases the cost of every future agent
  session (re-deriving context, following dead links) and risks repeating
  Phase 3/5's mistakes (#8 above) because the lessons aren't visible.
- **Generic fix options**: process a ledger-historian pass over the inbox;
  merge or reconcile `vm-pulled`-only content into `master` (at minimum,
  `variant_hypothesis_backlog.md` and the `single_family_winner_discovery_gate`
  closeout).
- **Benchification risk**: N/A.

---

## Failure classes named in the brief but not separately evidenced here

The following classes from the required taxonomy list were searched for but
have **no distinct evidence** beyond what's captured above (they may be
subsumed): "wrong path" → folded into #1; "poor decomposition," "timeout
handling" → no Aether-specific scored evidence found (see
`gap_report.md`); "official-runner integration mismatch" → see #9 and the
"native vs equivalent" distinction in `03`/`06`.
