# 01 — Executive Brief

## Goal

True 100% on Terminal-Bench 2.0, scored under benchmark-native conditions
(Linux/container, real Docker backend), with the harness driving an executor
model — target executor **GPT-5.4 mini**. "True" means: no benchmark-specific
shortcuts, no hidden-test leakage, no evaluator-as-oracle gaming, reproducible
on held-out tasks.

## State of the project, honestly

- The project has spent the last several weeks (mid-May → 2026-06-10)
  cycling through **at least four distinct architecture lines**
  (`03`, `04`): the original packet/route-manifest baseline, an
  "Active Evidence Kernel" (kernel_*.py modules), a 2026-05-30
  `winning_harness_v1` synthesized from family-level diagnostics, and a
  2026-06-05/06 "model-led substrate v1" (Layer-2 success auditor +
  success contracts on top of the kernel). A fifth line, MLPCP v2/v3, was
  initially purged from the master tree, but as of 2026-06-11, the official run
  runs, patches, audits, and pause state for MLPCP v3 have been pulled and preserved under
  `tracking/variants/mlpcp_v3/`. It is currently paused.
- **No certified/valid TB2.0 (or even full custom-suite) score exists for
  any of these as of HEAD.** The most concrete numbers we have are
  *family-level* diagnostics from 2026-05-30 (`06`):
  - filesystem/cwd: 0/6
  - service readiness: 0/3
  - context/reduction: 2/7
  - environment/toolchain: 4/7
  - tooling baseline: 4/7 (7/7 with a "combined guard" — see caveat below)
  - long-horizon artifact handoff: 6/6 (already solved)
- The 2026-05-18 "Goal 1" winner-discovery process (on the `vm-pulled`
  branch, more rigorous than 05-30's attempt) explicitly concluded
  **`winner_found = 0`** across 7 candidate mechanism families.
- The 05-30 `winning_harness_v1` implementation exists in code
  (`runner/packet04_route_manifest.py`, `blocks/orientation/phase6_doctrine.py`)
  but **every scored run (35/35, 13/13, 12/12, 2/2) came back INVALID** due to
  local Docker being unavailable on the Mac dev machine. It was never rerun
  on the Azure VM Docker backend that is *known to work* (used successfully
  in the 2026-05-17 tournament). Status: **HOLD**, not abandoned, not validated.
- "Combined Guard V1.5 with Contract-Aware Sentinel Repair"
  (`076ba7694`, 2026-05-17) is sometimes referred to as a "perfect
  tournament run," but the actual scoreboard was 6/12 overall, and the
  combined-guard variant hit its 2 target tasks but **regressed a sentinel
  (0/1)** — i.e. it should not have been promoted under the project's own
  rules. It is also a hardcoded, task-specific repair (injects a
  `lookup_customer_order` argument) — not a generalizable mechanism.
- The most recently-touched code (HEAD `f9accef6a` and its immediate
  ancestors `551d5fedf`, `7df1dc929`, `232fef973`) is "model-led substrate
  v1": `runner/active_evidence_kernel.py` + `kernel_layer2_audit.py` +
  `kernel_gates.py` + `kernel_recovery.py` etc. This passed unit tests and
  an adversarial code review (4 gaps found and fixed), and had a
  path-serialization bug fixed 2026-06-06. **It has never been run against
  any eval suite.**

## Target executor vs. planning model

Target executor for Aether's harness loop: **GPT-5.4 mini** (cheap, fast,
the model whose failures the harness must compensate for). Fable itself (and
subagents doing architecture audit, trace mining, eval synthesis, and
adversarial review) may be a stronger model — that's expected and desirable.
The harness must work *for* GPT-5.4 mini, not assume a stronger model bails
it out at runtime.

## Biggest blockers

1. **No working local certified eval loop.** Almost every "scored" run in
   the last month that mattered was invalidated by local Docker
   unavailability. The Azure VM Docker backend (`harnesseng-dev`) is the one
   confirmed-working certified backend, but it's on-demand
   (`scripts/deallocate_harnesseng_vm.sh`,
   `scripts/configure_harnesseng_vm_autoshutdown.sh` — **both referenced by
   AGENTS.md but missing from the repo**, see `gap_report.md`).
2. **Architecture churn without scored deltas.** Each new line
   (winning_harness_v1, model-led substrate v1, MLPCP v2/v3) was built
   before the previous line was scored. The "scoreboard is the source of
   truth" rule in `AGENTS.md` has not actually been followed in practice for
   ~4 weeks.
3. **The two worst-measured, best-diagnosed gaps (filesystem 0/6, service
   readiness 0/3) have concrete proposed fixes that were never implemented
   or scored**: `filesystem_cwd_path_normalization_wrapper_01` and
   `service_contract_first_receipt_closure_01` (both in
   `tracking/collab/variant_hypothesis_backlog.md`, only on `vm-pulled`).
4. **The canonical ledger is stale** (last entry 2026-03-29) while 27 raw
   handoffs sit unprocessed in `tracking/ledger/inbox/` through 2026-06-06 —
   so even people on this project don't have an up-to-date single source of
   truth; this packet is partly a substitute for that.
5. **Broken doc pointers**: `runner/README.md` points at
   `../docs/current_surface_map.md` and `../docs/deprecation_map.md`, neither
   of which exists. `AGENTS.md` points at
   `tracking/collab/variant_hypothesis_backlog.md`, which exists only on
   `vm-pulled`/`remotes/vm/push-master`, not on `master`.

## Strongest evidence available

- The BigAI trace-layer corpus analysis (`research/analysis/bigai_trace_layer/`,
  314 runs / 86 tasks, ~82% pass) — the single largest empirical reference
  point in the repo, using a planner/executor/verifier architecture.
- The 2026-05-30 family-level diagnostic run (`06`) — real, scored,
  Docker-valid, and gives a concrete priority order (filesystem and service
  readiness are the worst gaps, long-horizon handoff is already solved).
- The 2026-05-18 Goal-1 winner-discovery closeout (`vm-pulled`) — rigorous
  about certified vs. invalid-local-Docker provenance; a model of the
  bookkeeping discipline that should be followed going forward.

## Weakest assumptions currently floating around

- Antigravity's 2026-05-30 "Zero-Abstraction Engine" claims (<12 steps,
  $0.19/run, 92% cost reduction) are **predictions, not measurements** — and
  the one related lean/zero-abstraction run that *was* tried regressed by
  hiding evidence and using brittle anchors.
- "Combined Guard V1.5" being framed as a win (see above) — it has a
  sentinel regression and a hardcoded task-specific repair.
- The assumption that "model-led substrate v1" is the right next step simply
  because it's the newest code — it has zero eval evidence.

## Open questions Fable must resolve

1. Kill, merge, or rescue `winning_harness_v1`? It's implementation-complete
   but unscored — does it deserve an Azure-VM rerun before being shelved?
2. Is "model-led substrate v1" worth running through the eval suite next, or
   should effort go straight at the filesystem/service-readiness fixes from
   the backlog (which target the worst-measured, best-understood gaps)?
3. Should the paused MLPCP v3 session (runs, audits, and patches pulled to `tracking/variants/mlpcp_v3/`) be resumed/integrated, or should it be killed or merged?
4. What is the actual plan for getting a **repeatable, certified (Azure VM
   Docker) eval loop** running — this underlies everything else.
5. How should the stale ledger / inbox backlog be processed so future agents
   (and Fable's subagents) work from current truth, not 2-month-old docs?

## Immediate decision Fable must make

Before any new mechanism work: **decide the eval-loop story** (local-invalid
vs. Azure VM Docker vs. something new), because every recent "scored" claim
in this repo that matters is contaminated by this issue. Everything else —
architecture verdict, keep/kill/merge, failure-class closure plan — is
downstream of having a trustworthy way to score a candidate harness.
