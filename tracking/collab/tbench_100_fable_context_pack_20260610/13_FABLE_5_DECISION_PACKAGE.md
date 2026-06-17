# 13 — Fable 5 Decision Package (2026-06-11)

> Read-only audit at HEAD `f9accef6a`. All proposals below require user
> approval before any execution. Nothing in this file was executed —
> it is Fable's response to `12_FABLE_5_MASTER_PROMPT.md`.

---

Understood — planning only. My verification pass is complete; no execution was performed and none will be. Below is the full decision package.

# Aether → TB2.0 100%: Chief Architect Decision Package

**Fable, 2026-06-11. Read-only audit at HEAD `f9accef6a`. All proposals below require user approval before any execution.**

## Bootstrap findings — two load-bearing packet claims are wrong, and they change the plan

Before the required outputs, the spot-check results, because they materially reorder everything downstream:

**Correction 1 — the kernel wiring gap is already closed.** The packet (propagated through `01`, `03`, `05`, `08`, `10`, `gap_report.md`) claims `runner/agent.py` only reaches the old `evidence_kernel.py` and that `tools/run_final_harness_eval_suite_baseline.py` is hardcoded to `recipe_control`. At HEAD this is stale: [agent.py:1639](runner/agent.py:1639) defines `_is_active_evidence_kernel_route()` and dispatches active-kernel finalization at [agent.py:325](runner/agent.py:325) and [agent.py:543](runner/agent.py:543) for variant ids `active_evidence_kernel_v1` and `active_evidence_kernel_control_plane_context_v1`; the baseline runner defaults `variant_id="active_evidence_kernel_v1"` and routes manifests through `build_packet04_route_manifest` ([run_final_harness_eval_suite_baseline.py:271](tools/run_final_harness_eval_suite_baseline.py:271), `:326`, `:2899`). Lane 9's "route-manifest plumbing fix" is essentially done; the kernel is one CLI invocation away from being scored, not a wiring project away.

**Correction 2 — `winning_harness_v1` is not "unscored evidence sitting on the table." It was scored on the VM and it failed everywhere.** The packet's `06`#4 describes the 15:28 local-INVALID attempt and stops there. But the same-day 16:02 handoff ([160243_codex_winning-harness-v1-goal-build-and-four-surface-eval](tracking/ledger/inbox/2026-05-30/160243_codex_winning-harness-v1-goal-build-and-four-surface-eval_3d3827f56e.md)) records a **VM-certified rerun**: family board **0/35** (31 fail, 4 invalid), private suite **0/13**, benchmark board **0/12**, TB challenge **0/2** — with explicit inference "failure profile is capability/output failure rather than environment invalidity" and dominant reasons `grader_output_missing`, `bfcl_state_mismatch`, `terminalbench_verifier_failed`. Surviving run rows on master confirm `backend_ref: azure_vm_docker`, `authority_label: native` (e.g. `runs/20260530T154755Z/result_rows.jsonl`). Option 1's "cheap rerun" already happened; the answer was a wipeout. This converts Architecture C from "rescue candidate" to "certified-failed."

**Confirmed as stated by the packet:** `family_winner_registry.yaml` winners list is empty; the two VM lifecycle scripts are missing from `scripts/`; `_clean_hidden_refs()` exists and is applied in [kernel_layer2_audit.py:104-106](runner/kernel_layer2_audit.py:104); `EXPECTED_REMOTE_FRAGMENT` is enforced at [benchmark_adapter_terminalbench_native.py:35](runner/benchmark_adapter_terminalbench_native.py:35); the variant backlog and Goal-1 closeout exist only on `vm-pulled`; the 2026-05-30 family baseline rows (gpt-5.4-mini, `sc_b_01`) are recoverable from `vm-pulled`; and the MLPCP v3 pause state is accurate — I verified `qemu-startup` reward **1.000** and `extract-moves-from-video`/`install-windows-3.11` reward **0.000** in the pulled Harbor `result.json` files, all under eval id `mlpcp-v2-harbor__gpt-5.4-mini__terminal-bench`.

**One under-weighted fact that becomes the strategic centerpiece:** the MLPCP v3 lane is the **only place in the entire project where real TB2.0 tasks have been scored under the official Harbor framework with the actual target executor (GPT-5.4 mini)**. Everything else — the custom suite, the family diagnostics, the adapters — is proxy surface. The instrument the 100% goal must ultimately be measured on already exists, ran yesterday, and is paused.

---

## 1. Architecture verdict

Ranked by what the evidence actually supports (tiers per `08`):

**A. blocks/ baseline (flat_loop + raw_bash + guards) — real, measured, insufficient alone.** The only architecture with a full certified family-level scoreboard (2026-05-30: filesystem 0/6, service 0/3, context 2/7, env 4/7, tooling 4/7, long-horizon 6/6). It is the honest substrate: Terminus-shaped, generalizable, and the baseline every candidate must beat. Its measured weaknesses are precisely the three families with concrete proposed fixes. Merit: high as substrate and control arm. Merit as the final harness: no — 16/36-ish on the family board does not extrapolate to 100% on TB2.0.

**B/D. Active Evidence Kernel + Model-Led Substrate v1 — the best-engineered unknown, now cheap to measure.** Evidence tier: unit-test + adversarial-review only — by `08`'s rules this is *nothing*. But two things changed my prior versus the packet's caution: (a) it is already wired and is the baseline runner's default variant, so scoring it is an invocation, not a project; (b) its design center — `GOVERNED_STATUSES`, success contracts, Layer-2 audit with `_clean_hidden_refs`, deterministic finalization gates — is aimed at exactly the failure class (`ungoverned_model_claim` / finalization-truth) that a weak executor like GPT-5.4 mini exhibits most. Verdict: worth exactly one scored slice before any further investment. Not worth one more line of code before that slice.

**C. winning_harness_v1 — certified-failed, kill.** 0/60 scored rows on a valid VM backend across four surfaces. The synthesis-from-diagnostics method was sound; the composed artifact regressed. The packet's HOLD framing is obsolete.

**E. MLPCP v3 — wrong architecture lineage, but it owns the two most valuable assets in the repo.** As an architecture (cockpit/capability-graph/typed-tools continuity runner), it carries the same unscored-surface-area problem as B/D, plus a purged-v2 history. But it produced: (1) the **Harbor-native scoring bridge** (`mlpcp_v2_harbor_agent.py` / `mlpcp_v2_harbor_task_runner.py`, pulled under `tracking/variants/mlpcp_v3/`) — the only working benchmark-native TB2.0 loop; (2) the **only real TB2.0 pass with the target executor** (`qemu-startup` 1.0 after the receipt-memory-cockpit patch); (3) the cleanest new failure diagnosis in months: on hard tasks the model **ignored the provided background/service tools and looped on inspection** — a generic capability/affordance failure, not an environment one. And it documented one exemplary negative decision: the task-specific forced-escalation patch was *rejected as benchifying*. Verdict: kill the lineage, harvest the assets.

**F. final_harness_eval_suite — keep as inner loop, but it needs a health audit.** The 05-30 `recipe_control` runs scored 0 hard-task passes with `sentinel_gate: invalid` (`runs/20260530T154156Z/scoreboard.json`). Either the suite is calibrated far above current capability (plausible — they're "hardest" rows) or runner/grader plumbing is broken (`grader_output_missing` dominated the private surface). Until that's distinguished, the suite cannot discriminate between candidate harnesses. Separately, `terminalbench_verifier_repair` is known non-discriminating and `tool_result_attribution` has suspected fixture leakage (`07`#11/#12) — both flagged since 05-18, neither diagnosed.

**G. Native TB adapter — superseded for scoring, keep for provenance patterns.** The 05-18 audit's "equivalent, not native" finding plus the Harbor lane's existence means the fastest route to native authority is the Harbor bridge, not finishing this adapter. Its provenance-check pattern (`EXPECTED_REMOTE_FRAGMENT`) should migrate into whatever becomes canonical.

**H/I. Continuous-session patterns and BigAI — mine, don't build.** BigAI's reconstruction (`research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`) is doctrine-level gold for an 82%-passing system: planner/executor/verifier separation, verification as an external audit role, recovery-after-verifier-rejection as a *normal* loop, backup/isolation on state-sensitive tasks. Stop-Hook-style completion vetoes are functionally what `kernel_gates.py` + Layer-2 audit already implement. Nothing here justifies a from-scratch architecture; everything here justifies specific mechanisms inside the existing one.

**The meta-verdict:** the project does not have an architecture problem; it has a **measurement-allocation problem**. Four architectures were built; roughly 1.5 were ever scored. The two worst-measured failure families have had concrete, evidence-backed, generic fixes sitting in a backlog (on an unmerged branch!) since 2026-05-25/26. The fastest honest path to 100% runs through closing measured failure classes on one carrier architecture under one trustworthy scoring loop — not through a fifth architecture.

## 2. Keep / kill / merge / redesign

| Component | Decision | Rationale and conditions |
|---|---|---|
| blocks/ baseline (flat_loop, raw_bash) | **KEEP** | Permanent substrate and control arm. Every promotion is measured against it. |
| Active Evidence Kernel + Model-Led Substrate v1 | **KEEP — conditional, one scored slice** | It's the default route at HEAD; score it against the family board vs `sc_b_01` control. Beats control → it's the carrier. Ties/loses → demote to "finalization-gate library" grafted onto blocks, and stop maintaining two finalization paths. No new kernel code until scored. |
| `winning_harness_v1` (composed recipe) | **KILL** | Certified-failed 0/60 on valid VM backend (inbox 160243 + run rows). Salvage individual doctrines from `phase6_doctrine.py` only via the backlog process with their own predictions. Correct the HOLD record in the ledger. |
| Combined Guard V1.5 | **KILL as-is; preserve as regression fixture** | Certified sentinel regression + hardcoded `lookup_customer_order` repair (a `09` violation pattern). Keep the code frozen as the known-bad fixture Lane-3 sentinels must catch. Any successor must be schema-derived and generic. |
| MLPCP v2/v3 lineage | **KILL lineage / HARVEST three assets** | (1) Harbor bridge → generalize into an architecture-agnostic `aether_harbor_agent` that mounts any route-manifest variant; (2) receipt-memory-cockpit patch → re-express as a generic candidate mechanism in the context/evidence lane (it has the only real TB pass attached — but verify generality before crediting it); (3) background-tools + progress-escalation idea → redesign generically (see §4, class #10). Do not resume the v3 session as an architecture. |
| Route-manifest plumbing | **KEEP — verify, don't build** | Already fixed at HEAD per Correction 1. One `recipe_control` regression invocation to confirm, then mark Lane 9 done. |
| final_harness_eval_suite registry | **KEEP + REPAIR** | Inner-loop surface. Requires a suite-health audit first (why 0 passes + invalid sentinels under control? `grader_output_missing` = suite bug or harness bug?). Fix `terminalbench_verifier_repair` discrimination and `tool_result_attribution` isolation *before* any mechanism targets those families. |
| Native TB adapter (`benchmark_adapter_terminalbench_native.py`) | **MERGE into Harbor lane** | Harbor bridge becomes the canonical native scoring path (it is benchmark-native by construction). Port the provenance-check and `invalid_environment` classification patterns. Keep the adapter for calibration benchmarks (BFCL/ContextBench/Letta) where it's the only path. |
| `evidence_kernel.py` (legacy) | **DEPRECATE after Gate 1** | Whichever way the kernel slice goes, converge to one finalization path. Two parallel truths is how Phase-3-style mislabeling happens. |
| vm-pulled-only content (backlog, Goal-1 closeout, authority audit, family baseline rows) | **MERGE to master** | The project's canonical queue and its gold-standard bookkeeping example must live on the main branch. This is a no-code, high-leverage fix. |

## 3. Fastest implementation sequence

**The eval-loop problem (`07`#9) is a hard prerequisite for promotion-grade evidence — but it is a much smaller job than the packet implies.** The VM backend demonstrably works and was used as recently as yesterday (MLPCP Harbor runs, 2026-06-10/11). What's actually missing is: the two lifecycle scripts, a single standardized "score a candidate" workflow, and — critically — an **artifact persistence contract**, because the repo has now lost scored evidence twice (the 06-04 loop and the `__winning_harness_v1__gpt54_mini` family rows both survive only as `.pyc`). A scoring loop that loses its own results is as useless as no loop.

Sequence (numbers reference `10`'s options):

1. **Step 0 — Eval-loop hardening** (Option 1, reduced scope): recreate lifecycle scripts; one `score_candidate` workflow (VM up → run → sync `result_rows.jsonl`/`scoreboard.json`/traces back to repo → commit → deallocate); add a check that fails the run if result artifacts aren't synced. Skip the `winning_harness_v1` rerun — it already happened (Correction 2).
2. **Step 1a — Kernel first-score** (Option 3, now cheap): family board, `active_evidence_kernel_v1` vs `sc_b_01` control, GPT-5.4 mini, n≥2. This is Gate 1's input and decides the carrier.
3. **Step 1b — Harbor-native TB2.0 baseline** (parallel; replaces Option 5): generalize the Harbor bridge minimally to mount the current best harness; run the widest available TB2.0 task set at n=1 with the carrier candidate. This produces the project's **first true "X% on TB2.0" number** — the denominator of the entire mission. Without it, "100%" has no measurable meaning.
4. **Step 2 — The two backlog mechanisms** (Option 2): `filesystem_cwd_path_normalization_wrapper_01` and `service_contract_first_receipt_closure_01`, implemented generically on the Gate-1 carrier, scored A alone / B alone / A+B with BFCL + long-horizon + tooling-order sentinels.
5. **Step 3 — Suite-health and eval repair** (Lane 6, parallel with Step 2): diagnose `grader_output_missing`, verifier-repair discrimination, attribution leakage. Eval fixes precede any mechanism targeting those families (per `09` risk #4/#5).
6. **Step 4 — Context-family re-verification**: rerun the context family against the already-coded adaptive compaction fix (cheapest "is our recent work real" check), plus the generic progress-escalation mechanism from the MLPCP diagnosis, with `qemu-startup` as its green regression sentinel (exactly as the pause state prescribes).
7. **Step 5+ — iterate the loop** (§5) family by family toward the Harbor board, hardest-tail last.

Option 6 (new architecture) appears nowhere above; it is gated behind a ceiling finding (Gate 4, §7).

## 4. Failure-class closure plan

For each OPEN/PARTIAL class in `08` — mechanism, and the evidence tier constituting closure. Closure ALWAYS means: certified-pass on the family board **plus** named sentinels green **plus**, for the top families, transfer onto at least one real TB2.0 row via the Harbor lane.

- **Filesystem/cwd (0/6) — OPEN, top priority.** Mechanism: `filesystem_cwd_path_normalization_wrapper_01` as specced on `vm-pulled` (canonical-root resolution, relative-path canonicalization before filesystem actions and verifier handoff; no task-name logic) plus a workspace map injected at orientation. Closure: certified ≥5/6 on the family board, BFCL + dependency-config + verifier-repair sentinels green, and no regression on the Harbor calibration tasks. Benchification check: spec already passes `09` rule 1.
- **Service readiness (0/3) — OPEN.** Mechanism: `service_contract_first_receipt_closure_01` — but with one mandatory generalization before implementation: the backlog's normalization to `python3 service_runtime.py` is a task-shaped literal (`07`#2 flagged this; `09` rule 5). Re-derive process identity from the task's own visible config/contract, never a fixed string. Add protocol-level (not port-level) probes to fold class #3 in. Closure: the predicted 0/3→3/3 at certified tier, with the prediction recorded *before* the run; partial movement (1-2/3) is reported as a partially-failed prediction, not reframed.
- **Context/evidence carry-forward (2/7) — PARTIAL(code)/UNVERIFIED.** Mechanism already exists (adaptive compaction in `kernel_context_pack.py`). Action is measurement, not code: rerun the context family. If the receipt-memory-cockpit harvest proves generic, trial it here as a second candidate — separately, A/B. Closure: certified ≥5/7 with long-horizon + BFCL sentinels green (this family's predecessor regressed BFCL once — sentinel is non-negotiable).
- **Environment/toolchain (4/7) — OPEN.** Mechanism: `dependency_runner_resolution_contract_01` (generic interpreter/build-tool discovery at orientation). Sequenced after the two 0-families. Closure: certified ≥6/7, filesystem + verifier-repair sentinels green.
- **Tool-contract (tooling 4/7 with regressed guard; attribution 0/2) — OPEN/REGRESSED.** Precondition: Lane-6 eval diagnosis (leakage/isolation) before any mechanism — multiple variants all scoring 0/2 is as consistent with a broken eval as a broken harness. Then a schema-derived contract classifier (Goal-1's recommended `tool_call_contract_classifier`), explicitly tested against the Combined-Guard-V1.5 regression fixture. Closure: certified pass on a *repaired, discriminating* eval, plus `ctc_semantics_001_multi_required_order` sentinel green.
- **Finalization-truth (`ungoverned_model_claim`) — PARTIAL(code)/UNVERIFIED, most code-per-evidence in the repo.** No new code. Closure comes free with the Gate-1 kernel slice: instrument the run to report how often Layer-2 audit + gates *change* an outcome (block a false `governed_pass` / force useful continuation). If the gates never fire or only misfire, the entire substrate-v1 investment gets re-evaluated. Closure: certified evidence that gate interventions are net-positive on the family board.
- **Weak-proof/fake-artifact (UNKNOWN).** Blocked on Lane-6 strengthening `terminalbench_verifier_repair` into a discriminating eval (must fail a deliberately-bad control variant). Only then classifiable.
- **Loops/progress/efficiency (UNKNOWN, newly evidenced).** The MLPCP hard2 audits give this class its first concrete trace evidence: the model ignored provided background tools and looped on inspection. Mechanism: a **generic progress-escalation ladder** — harness-side no-progress detection (no new receipts/artifacts/state-deltas across N actions) triggering escalating *generic* prompts ("no new evidence in N steps; restate plan; list unused tools/affordances"), never task-specific tool forcing (correctly rejected as benchifying in the pause state). Closure: certified pass on a new no-progress homolog eval + `qemu-startup` green as regression sentinel + hard2-task movement at the Harbor tier.
- **Process classes (churn #8, stale ledger #13, infra #9).** Closed by §5's loop rules, the Lane-7 merge/historian pass, and Step 0 respectively. The artifact-persistence contract closes the "evidence-stripped runs" sub-failure that the packet's gap report documents twice.

## 5. Eval loop design

Two nested loops, one authority standard, one anti-churn rule.

**Inner loop (iteration, days):** family-level board + sentinels on the Azure VM, GPT-5.4 mini, n≥2 per row. Per AGENTS.md's autoresearch framing, every cycle is: *score → diagnose (Trace-Diff, classified per taxonomy) → hypothesize (backlog entry) → predict (written delta + named sentinels, committed before the run) → validate (A / B / A+B) → compare (vs frozen baseline + sentinel board) → learn (taxonomy + ledger update, failed predictions preserved verbatim)*.

**Outer loop (truth, weekly or per-promotion):** full available TB2.0 set via the generalized Harbor bridge, locked harness config, n≥2. This is the number that defines progress toward 100%. Official tasks are never iterated against (`09` rule 4) — the inner loop iterates on homolog families; the outer loop audits transfer.

**Authority standard (resolves certified-vs-invalid permanently):** adopt the 2026-05-18 audit rules as *mechanical preconditions, not conventions* — a result row may carry `admission_level: certified` / `backend_ref: azure_vm_docker` only if the run summary embeds `docker_preflight.available: true` captured during that run; rows failing the check are auto-labeled `invalid_environment` by the scoring tooling itself, so the Phase-4/5 mislabeling class becomes impossible rather than discouraged. Local Mac runs are debug-tier by definition; if a local inner loop is wanted later, Colima/Docker Desktop can be evaluated as an accelerator but never as authority.

**Anti-churn rule (closes `07`#8):** a hard work-in-progress limit of **one unscored architecture-level change at a time**, enforced at Gate level: no new mechanism implementation may start while a finished mechanism awaits scoring, and no new architecture line may be opened except through Gate 4. The scoreboard-vs-narrative discipline already exists in AGENTS.md; the gates in §7 are what make it binding.

**Artifact persistence contract:** every scored run syncs `result_rows.jsonl`, `scoreboard.json`, `run_summary.json`, and trace bundles back into `tracking/` and commits them in the same slice; the workflow fails loudly if sync produces only bytecode/empty dirs. (This rule exists because the repo demonstrably lost two runs' worth of scores.)

## 6. Subagent tasking plan (proposal — nothing dispatched)

Adapting `11`'s lanes; "strong" = Fable/Opus-class, "mid" = Sonnet-class, "exec" = GPT-5.4-mini-class (dogfooding).

**Wave 1 (immediately, parallel, all independent):**
- **Lane 5 (Run/Eval infra) — mid.** Recreate the two VM lifecycle scripts; build the `score_candidate` workflow with the docker-preflight precondition and artifact-sync check. Accept: a dry-run against the VM proving up→run→sync→deallocate, with correctly labeled authority fields.
- **Lane 7 (Context/ledger) — mid.** Merge `vm-pulled`-only canon to master (`variant_hypothesis_backlog.{md,yaml}`, Goal-1 closeout + authority audit, family baseline result rows); historian pass over the 27 inbox entries — **including correcting the `winning_harness_v1` record from HOLD-INVALID to scored-fail** (inbox 160243). Accept: no failed prediction or kill silently dropped; backlog readable from master.
- **Lane 1 (Architecture audit) — strong.** Trace both finalization paths end-to-end at HEAD (the "two paths" question `gap_report.md` §7 left open); confirm the route-manifest plumbing with citations; inventory exactly what a candidate variant needs to flow through the baseline runner. Accept: exact import chains/line numbers, no "wired in" claims without grep evidence.
- **Lane 8 (Harbor bridge audit) — strong.** Read the pulled `mlpcp_v2_harbor_agent.py`/`mlpcp_v2_harbor_task_runner.py`; produce the design diff for an architecture-agnostic `aether_harbor_agent` (mounts any route manifest); determine what TB2.0 task set the VM's Harbor checkout can actually serve (this is the biggest unknown in the whole plan). Accept: a concrete "what exists / what's missing / how many tasks runnable" report.

**Wave 2 (after Wave 1 lands, parallel):**
- **Lane 5 — Run A:** family board, `active_evidence_kernel_v1` vs `sc_b_01`, mini, n=2 (Gate 1 input). **Run B:** Harbor TB2.0 baseline with the current best harness, n=1 (first true % number). Accept: raw status surfaced, INVALID never reinterpreted as FAIL.
- **Lane 6 (Verifier/suite audit) — strong.** Diagnose `grader_output_missing` on the private surface; make `terminalbench_verifier_repair` discriminate (must fail a deliberately-bad control); diagnose `tool_result_attribution` isolation. Accept: "eval-broken vs harness-broken" verdict per surface, eval fixes proposed before any mechanism work in those families.
- **Lane 4 (Trace mining) — strong long-context.** Mine the already-local MLPCP hard2 audit bundles + BigAI `question_answers.json` for the no-progress/affordance-blindness class; emit a divergence report and the generic progress-escalation spec. Accept: AGENTS.md taxonomy classification with exact trace citations.

**Wave 3 (after Gate 1):**
- **Lane 2 ×2 (Implementation) — exec-class, separate worktrees.** Filesystem wrapper; service receipt closure (with the process-identity generalization mandated in §4). Accept: `09` checklist pass — one-sentence description naming no specific tool/file/task; held-out variation test included.
- **Lane 3 (Regression sentinels) — mid.** Sentinels that demonstrably fail against Combined Guard V1.5 (`076ba7694`), the BFCL-regressing long-horizon candidate, and the lean evidence-hiding probe. Accept: confirmed failures against all three known-bads.
- **Lane 11 (A+B integration) + Lane 5 (scoring) + Lane 10/12 (taxonomy + summaries)** per the standard loop.

Not delegated, ever: keep/kill/promote decisions, certified labeling, and anything that becomes canonical ledger content.

## 7. Stop/go gates

- **Gate 0 (infra):** `score_candidate` workflow produces one correctly-labeled, artifact-synced run end-to-end. **Stop:** no mechanism or scoring work proceeds to certified claims until this passes. If the VM itself is unreachable, the whole plan re-sequences around backend restoration — nothing else is worth doing first.
- **Gate 1 (carrier selection):** kernel vs control family-board result. Kernel ≥ control with gates demonstrably firing usefully → kernel is the carrier; demote `evidence_kernel.py`. Kernel < control or gates inert → blocks+guards is the carrier; kernel becomes a finalization library; **no further kernel feature work**.
- **Gate 2 (per-mechanism):** A / B / A+B scored with sentinels. Net-positive → promote (registry + ledger). Target moved but sentinel regressed → kill or iterate, never promote (the Phase-3 rule, this time enforced). Prediction failed → record it as failed.
- **Gate 3 (Harbor truth check):** after Wave-2 Run B and after every promotion, compare inner-loop gains against Harbor-board movement. Inner gains that don't transfer → suspect proxy-suite overfit (benchification of our own suite — same disease, private strain) and pause that family's lane for re-diagnosis.
- **Gate 4 (new-architecture gate, the Option-6 lock):** a new architecture line may open only with (a) two consecutive loop cycles where promoted mechanisms move the family board but the Harbor board has plateaued, plus (b) a written ceiling argument citing certified rows, plus (c) a stronger-executor contrast run showing failures are harness-limited rather than model-limited. Absent all three, building new architecture repeats Phase 5-7.
- **Gate 5 (the mini question):** if a task-tail persistently fails at the Harbor tier across ≥3 mechanism cycles, run the identical harness with a stronger executor on exactly that tail (diagnosis arm, not the scored lane). Stronger model passes → harness limit, keep working. Stronger model also fails → harness limit elsewhere or task-environment issue. Mini fails where the harness gives demonstrably complete affordances and a stronger model sails → that is the documented, evidence-grade "why not with 5.4 mini" case the mission brief demands — produced by measurement, not assertion.

## 8. First 72-hour execution plan (proposal)

Assumes parallel subagent lanes; all VM actions follow AGENTS.md lifecycle rules (deallocate at handoff).

**Hours 0–6 — unblock and correct the record.**
Wave-1 lanes dispatch in parallel: infra scripts + `score_candidate` workflow (Lane 5); vm-pulled merge + historian pass with the `winning_harness_v1` record correction (Lane 7); finalization-path/wiring audit (Lane 1); Harbor bridge audit incl. "how many TB2.0 tasks can the VM serve" (Lane 8). Fable: write the Gate-1 prediction *now*, before any run — predicted kernel-vs-control deltas per family, named sentinels.

**Hours 6–30 — first new certified evidence.**
Gate 0 check on the workflow. Then Run A (kernel vs control, family board, mini, n=2) and Run B (Harbor TB2.0 baseline, n=1) — independent, parallel VM jobs. Lane 6 starts the suite-health audit on the existing 05-30 artifacts (no VM needed). **This window is designed to produce the deliverable the window requires: Run A is new certified-pass/fail evidence on the biggest open question in the repo (is the kernel worth anything?), and Run B is the project's first true TB2.0 percentage.** If either run comes back INVALID, the cause analysis (preflight field, backend ref, sync check) is itself the certified-INVALID-with-clear-cause evidence — and Gate 0 gets fixed before anything else.

**Hours 30–48 — Gate 1 + mechanism build.**
Fable adjudicates Gate 1 against the written prediction; carrier selected; taxonomy updated (Lane 10). Lane 2 ×2 begins the filesystem and service mechanisms on the carrier in parallel worktrees; Lane 3 builds the three known-bad regression sentinels; Lane 4 delivers the no-progress divergence report and progress-escalation spec (spec only — implementation waits for its eval per AGENTS.md).

**Hours 48–72 — first mechanism scoring.**
Score filesystem-alone and service-alone (A and B) on the family board + sentinels, n=2. If both land green, queue A+B for the next cycle (don't rush the interaction test into hour 71). Lane 12 produces scoreboard deltas vs the 05-30 baseline; ledger updated; VM deallocated; 72-hour closeout written with: Gate-1 verdict, first TB2.0 baseline %, A/B results or their failure analyses, and the next-cycle plan.

Expected evidence yield by hour 72: ≥3 new certified scoreboards (kernel-vs-control, Harbor baseline, mechanism A/B), one corrected historical record, one merged canonical backlog — versus the prior four weeks' yield of zero.

## 9. Risks and falsification tests

- **Kernel underperforms control (Gate 1).** Likely enough to plan for: 16 modules tuned by unit tests, zero live calibration. Falsification is the run itself. Response is pre-committed: carrier = blocks+guards, kernel demoted to library — no relitigating.
- **Service fix misses 3/3.** The 0/3→3/3 prediction is the strongest in the backlog; if it lands 0-1/3, the family diagnosis (hidden-grader trace-shape mismatch) is wrong, and the response is Lane-6 eval re-diagnosis, not mechanism iteration. The required generalization of `process_identity` may also weaken the predicted lift — if so, that's the honest price of a generic mechanism, record it.
- **Harbor lane can't serve a meaningful TB2.0 task set** (only the ~4 pulled tasks). This would gut the outer loop. Response: Lane-8 report becomes the priority; fall back to hardening `benchmark_adapter_terminalbench_native.py` (Option 5) while expanding Harbor task acquisition. This is the plan's single biggest external dependency — flagged hour-6 deliverable for exactly that reason.
- **Suite-health audit finds the inner loop is broken** (`grader_output_missing` is a suite bug; sentinels structurally invalid). Then every inner-loop number including the 05-30 baseline needs re-validation, and eval repair preempts mechanism work entirely. Watch for this in hours 6–30.
- **Inner-loop gains don't transfer to Harbor (Gate 3 trip).** Indicates our custom suite has drifted from TB2.0's causal structure — respond by rebalancing homolog families against the Harbor failure tail, not by tuning mechanisms harder.
- **Progress-escalation regresses `qemu-startup`.** The pause state already names this sentinel; any regression kills that mechanism version outright.
- **Churn relapse.** The recurring failure mode of this project is Fable-shaped: a clever new architecture mid-cycle. The WIP-limit and Gate 4 exist to bind me as much as the subagents.

## 10. What evidence would change my mind

Ranked by fragility of the decisions above:

1. **The Gate-1 run** — flips the carrier decision either way; everything in §4 is carrier-relative. Re-check first if anything new arrives.
2. **The Lane-8 Harbor inventory** — if the full TB2.0 set is servable, the outer loop is real and the plan stands; if not, §3's sequencing reorders around adapter work. My "Harbor supersedes the native adapter" merge call rests entirely on this.
3. **The suite-health audit** — if the inner loop's 05-30 baseline is contaminated by runner/grader bugs, the family priorities (filesystem 0/6, service 0/3) could themselves be partly artifacts, and §4's ordering would need re-derivation from clean reruns.
4. **Row-level artifacts for the 16:02 winning-harness VM rerun** — my KILL verdict rests on one high-confidence actor handoff plus partial row survivals; the named run roots (`20260530T1556*Z`) are empty on master and `/private/tmp` paths are likely gone. If recovered artifacts showed that run was itself environment-contaminated, `winning_harness_v1` would move back from KILL to retest-required. (I judge this unlikely — the failure reasons are semantically capability-shaped — but it's the weakest link in a load-bearing call.)
5. **Generality of the receipt-memory-cockpit pass** — one task, one trial, n=1. If audit shows the patch encoded anything qemu-shaped, it gets no credit and the harvest reduces to the Harbor bridge + the failure diagnosis.
6. **The mini-ceiling question (Gate 5)** — I currently assume the measured failure classes are harness-closable with GPT-5.4 mini because they look like affordance/verification failures, not reasoning failures. The first stronger-executor contrast run on a persistent tail is the falsifier; if mini fails where the harness is demonstrably sufficient, the "prove why not with mini" case starts accumulating there.

---

**The winning solution, stated once, plainly:** one carrier architecture (kernel or blocks+guards, decided by Gate 1, not by recency), a Terminus-shaped loop with five generic capabilities layered on — workspace/path normalization, contract-first service receipts with protocol-level probes, evidence-preserving compaction, a finalization veto that only grants `governed_pass` against receipts, and a generic no-progress escalation ladder — iterated under a two-loop evaluation system whose outer truth is the official Harbor framework with GPT-5.4 mini, with promotion gated on certified A/B/A+B evidence and sentinels. That is not a new architecture; it is the project's own best pieces, finally pointed at its own best evidence, with the discipline it already wrote down and never enforced. The fastest path to 100% is the boring one: measure, close the 0-families, verify transfer, repeat — because the only thing this project has never tried for four straight weeks is finishing the loop.

---

## Plain-language summary

**What Fable found:**
Two of the packet's key "facts" were outdated:
1. The newer "kernel" code is actually already plugged in and ready to test — not stuck/disconnected as the packet thought.
2. The big "winning_harness_v1" attempt wasn't just untested — it *was* tested on the real cloud VM, and scored basically 0% across the board. Dead end, not a "maybe."

A bright spot: the recently-paused MLPCP work is the only place the project ever ran a real Terminal-Bench task end-to-end with the target model (GPT-5.4 mini) — and one task passed.

**Overall verdict:** The project doesn't need a 5th architecture. It has 4, and only ~1.5 were ever properly tested. The real problem is build → don't measure → build more. Stop building new things; measure what exists, fix the two best-understood weak spots, and use the one real benchmark runner that already works.

**The plan, in order:**
1. Fix the broken/missing "run an eval and save the results" pipeline (results have been lost twice already from not saving properly).
2. Head-to-head test: new kernel vs. old simple version. Winner becomes "the" system — decided by data, not recency.
3. Get a real "what % do we score on actual Terminal-Bench" number for the first time ever, using the one working benchmark runner.
4. Fix the two best-diagnosed weaknesses (agent gets confused about file locations; agent can't tell if background services are running) — both have ready-made fix designs sitting unused.
5. Check if parts of the test suite itself are broken (some scored 0% everywhere — could be a broken test, not a broken agent).
6. Repeat: test → diagnose → fix → re-test, with strict rules against "looks better" claims unbacked by real scores.

**Guardrails Fable set for itself:**
- No new architecture unless there's hard proof existing ones have hit a ceiling.
- Every "we improved X" claim needs a real before/after score, not a unit test or vibes.
- Only one big change tested at a time, so you know what caused the improvement.
- If a mini model keeps failing at something even when the harness gives it everything it needs, that's the evidence for needing a bigger model — not an assumption.

**Bottom line:** Nothing was run or changed — this is a proposed plan awaiting approval. Core message: stop inventing new systems and finish testing what's already built — that's the fastest real path to 100%.
