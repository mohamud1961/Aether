# Fable 5 — Adversarial Audit of Aether-Next (2026-07-08)

Auditor: Fable 5 (principal-architect audit session, read-only).
Scope: full repo at branch `codex/canonical-aether-consolidation`, HEAD `6f950cb3`, working tree as found on 2026-07-08.
Method: governing docs read in full; haiku subagents used for mechanical context collection; every load-bearing claim below re-verified by direct reads of code, traces, verifier evidence bundles, official task definitions, and by recomputing run provenance. Citations are `file:line` in the current working tree.

**One decisive fact frames everything in this report:** the current uncommitted `aether_next_build/aether_next/` package hashes to `d559c7dc4070…` under `run_pilot._tree_hash` — **byte-identical to the `code_tree_hash` recorded in both sentinel runs** (`vm_goal_runs/20260707T152214Z_sentinel/results.json`, `…162100Z_sentinel_steps200/results.json`). The working tree is not "unproven fixes written after the failures." It is exactly the code that scored 2/5 with 3 verifier false-cleans. Everything below reads the tree in that light: this is the measured state of the *latest* harness, not a stale snapshot.

---

## Executive verdict (read this if nothing else)

1. **The architecture is the right interpretation of the vision.** Role boundaries are real in code, not just docs: state-only verifier packets with a runtime leak assertion, verifier-gated completion, fail-closed architect config, post-termination grader mounting, no task-name branching anywhere on the certified path. Three prior audits and this one agree on that much, and I verified it independently.
2. **The binding constraint on TerminalBench score is no longer missing harness mechanism — it is verifier-model judgment quality.** The three false-cleans happened *through* live, runtime-enforced inspection gates, under architect configs that explicitly named the exact failure that then occurred. The verifier inspected the right evidence and drew the wrong conclusion, at 0.89–0.97 confidence, three times out of five.
3. **The vision and 100% do not fundamentally clash for the failure classes actually observed.** Two of the three false-cleans (kv-store-grpc, gcode-to-text) are recoverable with generic, in-vision mechanism (a falsification protocol on the completed verdict — structure, not judgment). The third (video-processing) is partially recoverable and partially a genuine model-capability ceiling, which the vision instructs us to accept rather than compensate for. I found no observed failure whose fix requires benchmark-specific logic.
4. **The operational discipline around the code has collapsed, and that is the most urgent problem.** The canonical-target decision, the governing vision doc, the EnvMap cleanup, the entire verifier-gate layer, and the sentinel evidence are all uncommitted. HEAD still says `harness/aether2/` is the active line. The suite is broken at collection by an untracked test that was never run. The ledger's model claim (mini) contradicts machine provenance (PRO deployment env). ~4 GB of scratch/backup/duplicate trees sit in the repo root. The code deserves more trust than the tree state currently earns it.

Recommendation in one line: **keep this codebase, commit it honestly, delete the scrapheap, and spend the next capability slice on verifier falsification discipline — with a scored known-bad eval — before any new feature work.**

---

## A. Decision-making audit

### A1. The canonical-target decision (Aether-Next over Aether-2) — right call, correctly derived, dangerously unrecorded

The decision trail is coherent and better-documented than most of this repo's history:

- `docs/CURRENT_ARCHITECTURE_VS_TARGET_ARCHITECTURE.md` (2026-07-02) maps both lines and explicitly defers the target choice.
- `docs/AETHER2_CARVE_DOWN_BUILD_PLAN.md` + `AETHER2_SLICE0…SLICE9` (2026-07-02 → 07-03) select `harness/aether2/`, execute nine slices with green suites and per-slice evidence, and complete a local sentinel (`SLICE9`: fsent_02 score 1.0, "no promotion claim" — honest).
- `docs/PRODUCTION_HARNESS_DECISION_BRIEF.md` (updated 2026-07-03 03:43) compares the lines on observables (Aether-Next: 245 tests, real TB runs 07-01, python3-compatible; Aether-2: 154 tests, 9 days staler, needs 3.10+) and recommends Aether-Next. It also correctly identifies that stale `CLAUDE.md` governance caused the aether2 mis-targeting in the first place.
- `docs/CANONICAL_AETHER_CONSOLIDATION_PLAN.md` (07-03 04:44) locks it. The carve-down build plan itself carries a "Superseded, 2026-07-03" header pointing forward.

So: **evidence-backed at the time, still valid, and followed through in practice** — every commit from `052dba66` through `6f950cb3` targets `aether_next_build/`. The AETHER2_SLICE lineage is genuinely dead as a production plan and says so itself; it is not a live contradiction. Two caveats the owner should hear plainly:

1. **The decision of record is not in history.** `git diff HEAD -- CLAUDE.md` shows the entire Governing Vision section and the canonical-target decision are uncommitted modifications; committed CLAUDE.md still declares `harness/aether2/` the active line. `docs/HARNESS_VISION.md` — the document that "outranks convenience" — is untracked (`??`). AGENTS.md's canonical-line section is likewise uncommitted (+71 lines). A fresh clone of HEAD reproduces the exact governance staleness that PRODUCTION_HARNESS_DECISION_BRIEF diagnosed as the root cause of the last mis-targeting. This is the single most self-defeating omission in the repo.
2. **The Aether-2 carve-down code changes are in limbo.** ~35 modified files under `harness/aether2/` plus ~20 untracked slice modules (`ahp_startup.py`, `receipt_driven_variant.py`, `adaptive_profile*.py`, …) implement the slices the docs describe, uncommitted. Under the standing decision they are reference material; they should be committed as reference (or reverted), not left as working-tree noise that inflates every future diff.

### A2. "Architect v2A doctrine" — does not exist in the repo

`grep -rn "v2A" docs/ aether_next_build/` returns nothing. Whatever "v2A" meant in chat threads, no artifact carries it. The architect doctrine that *does* exist and is followed through in code: `WORKBENCH_ARCHITECT_SYSTEM_PROMPT` ([workbench_hooks.py:14](aether_next_build/aether_next/workbench_hooks.py)) plus `ARCHITECT_PROMPT_CONFIG_AUDIT_20260704.md`. Lesson for the decision trail: doctrine that lives only in chat is not a decision; several of this project's "decisions" exist nowhere a future session can find them.

### A3. EnvMap cleanup and truthfulness slices — real, live, tested, uncommitted

Verified present in the tree and *in the sentinel runs* (tree-hash identity):

- `grader_hints` is now hardcoded empty at [envmap_builder.py:593](aether_next_build/aether_next/envmap_builder.py:593); the architect request filters benchmark-shaped metadata (`_model_facing_task_metadata`, [kernel_messages.py:73-120](aether_next_build/aether_next/kernel_messages.py)) and instead exposes high-recall visible materials, capability requirements, action affordances, observed environment support, and reviewer probe support — this matches the owner's "high-recall, not minimal" correction, with the truthful/inferred/unknown separations intact (`network_scope` unknown-until-probed, `inferred_not_fact` marking).
- Truthfulness: full-output spooling with head+tail markers and timeout-partial preservation (P2f), `read_output` as a verifier inspection kind, package-contract probing (`_python_package_contract`, [environment_probe.py:217-302](aether_next_build/aether_next/environment_probe.py)).
- Tested: `test_envmap_cleanup.py` and `test_runtime_truthfulness_slices.py` are collected and pass (see A4 suite note).

But: all uncommitted, ledger not updated past session 4, and the `grader_hints` *field skeleton* still exists ([runtime_ir.py:109,127](aether_next_build/aether_next/runtime_ir.py), threaded through [real_executor.py:453](aether_next_build/aether_next/real_executor.py:453) and consumed by `analysis.py`) — a half-finished removal.

### A4. The P0→P2→Ext→Road sequence — followed through, then discipline broke at the finish line

Road items 1–3.7, 5, 7 verified against commits and code (validation3 3/3 was real; verifier economics memoization exists at [kernel_verifier.py:131-158](aether_next_build/aether_next/kernel_verifier.py); `perceive_artifact`/`read_output` exist and were used live). Where the record and reality diverge:

- **Size caps (road item 6) regressed uncommitted**: docker_runner 693→**726**, model_hooks 446→**673**, compiler 606→**622**. envmap_builder grew to **599**. Six modules now violate the cap (§C).
- **The suite is broken at collection**: untracked `tests/test_sentinel_proof_board.py:5` imports `build_row` from `scripts/build_sentinel_proof_board.py`, which has never exported it (actual exports: `build_rows_from_file`, `write_outputs`). `python3.11 -m pytest tests -q` aborts with a collection error; nothing runs. Excluding that file: **338 passed, 12 skipped**. A test that cannot import was left in the tree — it was never executed by its author. That is exactly the "looks done" pattern this project's own No-Fake-Work standard prohibits.
- **Sentinel evidence hygiene**: both ledger inbox notes (`tracking/ledger/inbox/20260707T160900Z_sentinel_run.md`, `…164500Z…`) say the runs used **gpt-5.4-mini**; machine provenance in both results.json records `solver_deploy_env` and `architect_deploy_env` = **`AZURE_OPENAI_GPT54_PRO_DEPLOYMENT`** (the run_pilot defaults are the MINI envs, so PRO was passed explicitly). One of these is wrong, and it matters for interpreting a 2/5: false-cleans under pro are worse news than under mini. The first note even reasons about "PRO models requir[ing] larger verifier timeouts" while claiming mini. Additionally `code_sha` is empty (`git_available: false` on the VM) — the SHA-stamping invariant (`ROAD_TO_100.md` "Standing invariants") did not hold; only the tree hash saved the evidence chain. **Resolve the deployment-name→model mapping and correct the ledger; until then the sentinel model identity is unverified.**

Bottom line for §A: decisions were made well and mostly executed; the *recording* of decisions and evidence — the thing that lets a multi-agent project survive its own session boundaries — is currently the weakest layer of the system.

---

## B. Code / architecture audit (adversarial)

Read directly: kernel, kernel_config/turns/dispatch/messages/verifier, verifier + inspector + packets + probes + overlay, model_hooks, model_prompts, workbench_config/compile/hooks, envmap_builder, environment_probe, task_capability, classifier, run_adapter, docker_runner, run_pilot, result_metrics.

### B1. What genuinely implements the doctrine (verified, not vibes)

- **Verifier judges state, not story**: `build_verifier_packet` is state-only with a hard leak assertion over 18 forbidden solver-journey fields ([verifier_packets.py:206-228](aether_next_build/aether_next/verifier_packets.py)). Solver claims physically cannot reach the verifier.
- **Completion authority**: the workbench path completes only on a verifier `completed` verdict ([kernel.py:327-336](aether_next_build/aether_next/kernel.py)); a missing verdict at submit records `verifier_required_for_completion` (kernel.py:423). Solver self-report has no authority anywhere on the certified path.
- **Fail-closed judgment layer**: architect failure → `config_invalid`, no default config ([kernel_config.py:229-242](aether_next_build/aether_next/kernel_config.py)); certified adapter rejects non-workbench architect modes with no bypass; config repairs are recorded and surfaced as `architect_defect` result fields rather than laundered.
- **Grader isolation**: solver container starts with only the workspace mounted ([docker_runner.py:263-275](aether_next_build/aether_next/runners/docker_runner.py)); `/task` and `/tests` are docker-cp'd in **after agent termination** (docker_runner.py:390-402); grading runs post-terminal with `graded_after_timeout` handling so timeouts still get scored (docker_runner.py:359-376). The 07-04 audit's P0 mount leak is genuinely fixed.
- **Genericity**: zero task-name control flow in the canonical package (all grep hits are comments citing past failures, e.g. classifier.py:312, docker_runner.py:363-364). No upward imports (`grep 'from runner\.\|from eval_suite\.'` over the package: empty). Model-visible prompts explicitly forbid benchmark/hidden-test framing (workbench architect prompt; `VERIFIER_RUNTIME_CONTRACT` rules, [model_prompts.py:78-88](aether_next_build/aether_next/model_prompts.py)).
- **Runtime-enforced verification discipline** (this is stronger than any prior audit credited): a `completed` verdict with no inspection triggers forced default inspections ([model_hooks.py:534-567](aether_next_build/aether_next/model_hooks.py:534)); still-uninspected completion is *refused* and converted to `uncertain_missing_evidence` with a blocking finding (model_hooks.py:636-667); a shape-only inspection triggers a semantic-grounding retry (model_hooks.py:585-607); prose and structured missing-evidence requests are auto-realized into real `read_file`/`perceive_artifact`/`read_output` inspections (model_hooks.py:500-533, 608-635). All of this was live during the sentinel runs.

### B2. Where the code only *looks* like the doctrine — the decisive-evidence gap, precisely characterized

The three prior audits converged on "the verifier does not require evidence that can falsify the candidate answer." **Confirmed — with an important refinement they missed:** the harness now *does* force inspection, and the architect *does* configure falsification-aware contracts. What fails is the verifier model's execution of the comparison, and the gates cannot see that:

- The inspection-required gate is satisfied by **any** inspection (`inspected` is a boolean; one `perceive_artifact` of a solver-authored contact sheet counts — model_hooks.py:540-567).
- `_completed_inspection_is_semantically_grounded` (model_hooks.py:303) checks that inspections touched result-bearing evidence, not that the evidence could contradict the claim. Reading the proto file is "grounded"; failing to compare it to the spec is invisible.
- The verifier prompt contract has the right sentences ("Shape-only checks … never sufficient"; "Numeric agreement between two runs of the same method proves nothing"; "test the deliverable against YOUR OWN inputs" — model_prompts.py:85-87,121) but nothing structural makes the model *demonstrate* it obeyed them. All three false-clean verdicts violate at least one of these rules while formally passing every gate.

Secondary findings on this surface:

- **Half-wired verdict taxonomy**: uncommitted code accepts 14 verdicts ([verifier.py:10-25](aether_next_build/aether_next/verifier.py)) while the model-visible contract still advertises exactly 5 (model_prompts.py:59-65). Nine verdicts are accepted-if-emitted but never offered — inconsistent contract, added after which run? Neither: it was live during the sentinel (tree hash) and simply never exercised.
- `classify_verifier_outcome` (verifier.py:194-241, uncommitted) is keyword-matching over verdict prose (`TOOL_FAILURE_WORDS` etc.). Today it only labels receipts — acceptable as audit metadata, but it is exactly the kind of brittle prose-inference that must never gain authority. Watch it.
- Dead defensive branch: `_default_completion_inspection_requests` reads `packet["latest_file_reads"]` and `packet["artifact_evidence"]` (model_hooks.py:209-223) — fields the packet builder *asserts can never exist* (they're in the forbidden set). Unreachable code born of belt-and-suspenders confusion.
- The verifier's `read_file` inspection spans 4,000 chars ([verifier_inspector.py:271](aether_next_build/aether_next/verifier_inspector.py)). For gcode-to-text the decisive artifact was 1.66 MB; the verifier read three 4k windows of it and "confirmed" a header comment. The right tool existed (overlay_run_command: write your own decoder) and nothing steered the verifier to it when direct reading was structurally insufficient.

### B3. Ownership blur and residual duplicate paths

- **Legacy architect path still co-resident in the canonical package**: `ARCHITECT_SYSTEM_PROMPT` (the old ir-mode prompt with `workflow_policy`/`proof_plan`/`check_plan`, [model_prompts.py:7-44](aether_next_build/aether_next/model_prompts.py:7)) is live code invoked via `ModelHooks.architect()` ([model_hooks.py:356](aether_next_build/aether_next/model_hooks.py:356)) from [kernel_config.py:60](aether_next_build/aether_next/kernel_config.py:60). It is fail-closed off the certified path (run_pilot offers only `workbench`; `ensure_certified_architect_mode` rejects the rest), but P1a's "physical quarantine" claim is only true for contract mode. The ir-mode architect, `RuntimeConfigIR`'s config-side vocabulary, and the non-workbench completion path ([kernel.py:337-343](aether_next_build/aether_next/kernel.py:337) — gate-only completion when no workbench architect exists) are a second, physically present judgment lineage kept alive for tests. It should live in `reference_legacy/` or the tests should be rewritten onto the workbench path.
- **Harness text steering the verifier conversation**: the runtime gates inject instructions mid-dialogue (model_hooks.py:552-560, 573-578, 596-601). I judge this defensible — it is protocol enforcement with task-agnostic wording, the model remains the judge — but it is the closest thing to shared ownership on the certified path and each added instruction should pass the stronger-model test explicitly.
- **Architect prompt as a single 30,757-character line**: the uncommitted change flattened the readable triple-quoted `WORKBENCH_ARCHITECT_SYSTEM_PROMPT` into one line ([workbench_hooks.py:14](aether_next_build/aether_next/workbench_hooks.py); max line length 30,757; file now "105 lines"). The 500-LOC cap is being satisfied by formatting. The prompt is now undiffable and unreviewable — for the one artifact where review quality matters most. This is cap-gaming, and it should be reverted regardless of what else happens.
- Advisory mechanisms nothing enforces (by design, and correctly so — listing for completeness): `expected_steps`/`step_efficiency`, `automatic_memory_advisory`, no-progress advisories, `schema_humility` audit field, `alignment_board.py` (post-run), `architect_quality.py` (offline scorer). None gate anything. Verified.

---

## C. Bloat / minimality audit — the owner's "why is it so big" question, answered with numbers

**The agent is not big. The repo is.** Split the question:

### C1. The canonical agent: 16,009 LOC across 59 modules

For what it does — typed config compilation, docker substrate, spooled truthful I/O, 12-kind read-only verifier inspection surface incl. sandboxed overlay execution and vision, receipts/ledger/traces, failure classification, provenance — 16k LOC is *lean*. Reference points in this same repo: `harness/aether2/` is 29,604 LOC / 101 files for less capability; eval_suite is 17.9k; tools/ is 8.7k. The genuinely load-bearing certified path (kernel* + verifier* + workbench* + compiler/context + executors + runner) is roughly 10–11k; the remainder is capability surface (probes, overlay, vision lane, metrics, classifier, alignment audit) — **the right kind of big** under the vision, because each piece extends what the verifier or solver can *observe*, not what the harness *decides*.

The wrong kind of big inside the package (deletable/movable with confidence):

- Legacy ir-mode architect lineage: `ARCHITECT_SYSTEM_PROMPT`, `ModelHooks.architect`, `_baseline_resolve` path, non-workbench completion branch (§B3) — move to `reference_legacy/` with its tests.
- `grader_hints` vestige: field + plumbing + `analysis.py`'s consumption of a now-always-empty dict.
- Dead branches: forbidden-field reads in `_default_completion_inspection_requests` (model_hooks.py:209-230).
- 9 advertised-nowhere verdicts (either advertise or drop; a 5→14 taxonomy nobody is told about is surface without function).

**500-LOC cap violations, current tree (CLAUDE.md mandate):** `runners/docker_runner.py` 726, `model_hooks.py` 673, `compiler.py` 622, `envmap_builder.py` 599, `runtime_ir.py` 543, `execution.py` 512. Three of these were *fixed* at commits `e855e05c`/`c082095a` and regrew in the uncommitted work; and note the cap is only nominally honored in `workbench_hooks.py` via the 30k single-line string (§B3).

### C2. The repo: ~4 GB of scratch, five copies of the package, and 59 top-level reports

Should never have been left in the working tree (delete or move to external archive; none are referenced by canonical code):

| Path | Size | What it is |
|---|---|---|
| `pro_55_full_package_20260623T163542Z/` | 1.6 G | June 23 handoff bundle (49,968 files) |
| `tracking/local_runs/` | 1.5 G | 45k files of old run artifacts |
| `aether_next_build_backup_20260707_1414/` | 415 M | full package copy from 07-07 (its one useful fact — the pre-sentinel diff — is now recorded here) |
| `final_handoff_20260623T150104Z/` + `…150931Z/` | 312 M | two near-identical June 23 handoffs |
| `aether_next_vnext_takeover/`, `…final_offline_gate_baseline/`, `…verifier_policy_baseline/` | 21 M | June 29 experiment trees, nested copies of the package |
| `aether_next_build_pre_phase1_backup_20260629_214201/` | 4.1 M | another full copy |
| `tmp_archive/`, `build/`, `audit_output/`, `vm_pulled_runs/`, `jobs/` (empty), `Archive 2.zip`, `pro_workspace_aether_next/` | ~16 M | assorted dead scratch |
| `PROMPT_AUDIT_*` (6 files), `RECEIPT_DRIVEN_FULL_VARIANT_*` (4 files) | ~220 K | June 22 aether2-era audit outputs, superseded |

Also: **59 top-level `.md` reports inside `aether_next_build/`** (PHASE2_*, CHATGPT_*, audits, plans). These are real evidence, wrongly located — they belong under something like `aether_next_build/reports/` or `research/`, and several duplicate content (e.g., 32 MB git-pack files and a 17.5 MB PDF duplicated ×4 across snapshot dirs inside backups). `runner/aether2/` is 5 files / 18 LOC of stubs — delete. Live evidence to keep and commit: `vm_goal_runs/2026070*` (both sentinel dirs), the ledger inbox notes.

Answering the owner directly: *"why is there so much legacy slop/debt. why isn't it minimal. or is that not possible?"* — Minimal **is** possible and the canonical package is already close to it; the slop is (a) session-boundary residue nobody was assigned to delete (backups, handoffs, experiment trees), and (b) two decision-superseded lineages (aether2 mods, vnext trees) parked in the working tree instead of committed-as-reference or removed. This is a janitorial problem, not an architectural one — but it has real costs: it hid the fact that the suite was broken, it makes every `git status` unreadable, and it stores five divergent copies of the truth.

---

## D. Latest-run root-cause audit (independently verified, per task)

Evidence base: `vm_goal_runs/20260707T152214Z_sentinel/` (run A, 5 tasks, max-steps 30) and `…162100Z_sentinel_steps200/` (run B, 2 tasks, max-steps 200). Verifier bundles under `verifier_evidence/<task>/step_NNNN_solver_submit/`; final workspaces under `snapshots/`; ground truth from `official_tasks/<task>/`. Model per provenance: PRO deployment env for solver+architect (ledger says mini — unresolved, §A4). Combined best: **2/5 official passes**, 3 false-cleans — matches the brief.

### D1. log-summary-date-ranges — PASS, and a genuine exemplar
Reward 1.0, 4 steps, aligned. The verifier's verdict (verifier_evidence/…/parsed_verifier_result.json) shows real independent discipline: read `summary.csv`, read the recomputation output, **and sampled raw boundary-date log files** to confirm inclusive-range semantics at line level. This is what right looks like; the system can do it. Root cause of success: model + workbench, no harness assist. Classification `none` — correct.

### D2. video-processing — verifier false-clean; solver wrong; partially a model ceiling
Official: takeoff must be in [50,54], landing [62,64] (`official_tasks/video-processing/tests/test_outputs.py:97-98`); solver output 72/90; grader failed the range asserts. Verifier: `completed`, confidence 0.94, after **one** inspection — `perceive_artifact` of `/app/jump_probe.jpg`, a **solver-authored** contact sheet around the solver's own frames. Its stated reasoning ("frames around 72 show the athlete leaving the scene, while by 73 onward the athlete is absent") is self-contradictory with landing at 90 and describes frame-exit, not takeoff. The architect config had named the exact trap: *"A detector can appear plausible while being validated only by the same method that produced it"* — but its own `minimum_completion_evidence` asked for "a separate frame spot-check **around the reported** takeoff and landing frames," i.e. a solver-anchored, unfalsifiable check.
**Root cause: solver model capability (wrong event detection) compounded by verifier false-clean (self-confirming perception anchored to solver-chosen frames).** Harness contribution: none blocking; the verifier had `overlay_run_command` + `perceive_artifact` and could have swept frames itself. Classification on the row is `none`/`verifier_false_clean` — the alignment field carries the truth; correct per the established discipline.

### D3. gcode-to-text — verifier false-clean; purest "proxy evidence accepted as decisive"
Official answer: `flag{gc0d3_iz_ch4LLenGiNg}`, obtainable only by rendering the toolpath (official solution installs opencv+pytesseract and OCRs the geometry). Solver wrote `Embossed text` — the operand of an `M486 A…` object-labeling line, i.e. **metadata**. Verifier: `completed`, 0.89, calling `M486 AEmbossed text` "the **decisive** header region." The architect config had named this failure twice: *"The solver infers the answer from filenames or metadata instead of the actual printed text"* and *"The solver stops after inspecting comments even though the toolpath evidence would contradict or refine them."* The verifier violated its own written contract with the word "decisive" in its mouth.
**Root cause: solver semantic shortcut + verifier failure to require falsifying evidence.** Note the structural aggravator: read_file's 4k span made direct decisive reading of a 1.66 MB file impossible; the in-vision escape (author its own decoder in the overlay) was available and unused.

### D4. kv-store-grpc — run A honest incomplete; run B the cleanest possible false-clean
Run A: 30 steps, never submitted, no verifier round; classifier `harness_context_failure` (low confidence, "harness did not surface a real attempt") — honest refusal to blame the model without evidence, per the classifier's evidence bar ([classifier.py:272-294](aether_next_build/aether_next/classifier.py)).
Run B: solver did the entire task in **two mega `run_command` steps** and submitted at step 2. Final workspace proto (snapshots/…/final/kv-store.proto): `SetValRequest { string key = 1; int32 val = 2; }`. The visible instruction requires *"SetValRequest that includes a key (string) and a **value** (int)"* (`official_tasks/kv-store-grpc/instruction.md`). Official test calls `SetValRequest(key="handshake", value=999)` → ValueError. Verifier: `completed`, 0.97, whose summary **recites the wrong field approvingly** ("SetValRequest has string key and int32 val") with the spec text sitting in its own packet (`task_prompt` is a packet field). Its live RPC probe used clients built from the solver's own generated stubs — the self-confirming method the architect's own `false_positive_risks` warned about ("the proto can look correct by name while the message field types or RPC signatures are wrong"), though the architect's `minimum_completion_evidence` also prescribed that stub-based probe.
**Root cause: solver spec-misread + verifier failure to perform an available, trivial, decisive comparison (two short texts).** No perception, no big artifacts, no missing tool. This task is the type specimen for the falsification-protocol fix (§F).

### D5. code-from-image — run A honest incomplete; run B genuine pass
Run A: 30 steps, 5 solver protocol errors (turn kinds like `run_command`/`inspect_artifact` emitted as turn kinds — trace + results `model_parse_errors`), never submitted; `harness_context_failure`, honest. Run B (200 steps): pass at step 25, verifier verdict grounded in its **own** perception of `/app/code.png` cross-checked against the output hash — the vision lane working as designed, aligned with the grader.
**Root cause of A: step budget too small for this model's working style + residual turn-protocol friction** (the batch5 ergonomics fix reduced but did not eliminate protocol errors; all were retried successfully). Not a capability failure — proven by B.

### D6. Confirming/correcting the three-audit finding

**Confirmed:** the verifier accepts structurally-valid, self-confirming, and metadata/proxy evidence as decisive; all three false-cleans fit. **Corrected/refined in three ways:** (1) it is *not* an absence of inspection or of enforcement mechanism — runtime gates forced inspection and were live; the miss is inside the verifier model's comparative judgment, which current gates cannot observe. (2) The architect layer is *not* a co-culprit — its configs named the exact failure modes in all three cases; its only defect is occasional self-confirming *minimum-evidence wording*. (3) The runs' model identity (mini vs pro) is unverified due to the ledger/provenance contradiction — and if PRO is correct, this is evidence that scaling the verifier model alone does not close the falsification gap, which strengthens the case for the structural protocol in §F.

---

## E. Vision-fidelity verdict

Scored against the owner's four words, evidence per line:

- **Generic — 9/10.** No task-name control flow (verified by grep, comments only); no benchmark vocabulary reaching models (architect request filters benchmark-shaped metadata; prompts forbid hidden-test framing); grader strictly post-terminal (mount-after-termination verified in code and runner.log). Deduction: keyword vocabularies in task_capability/envmap remain benchmark-*shaped* (acceptable watch item, as Phase 0 already judged), and the ir-mode lineage still ships in the package.
- **Minimal — 6/10.** Canonical path is close to minimal for its capability set; deductions for: co-resident legacy architect path, grader_hints vestige, dead branches, 6 size-cap violations (3 regressed), the 30k-char single-line prompt, and — at repo scope — the 4 GB scrapheap and five package copies. The *agent* earns an 8; the *tree* drags it down.
- **Capable — 7/10.** The verifier can genuinely observe state: files (paged), outputs by handle (spooled, truthful), live ports/HTTP/processes, artifact metadata incl. permissions, images via its own vision, and arbitrary read-only execution in a disposable overlay with its own fixtures. Context is lossless at the substrate (P2f verified). Deduction: the capability that matters most — compelling *decisive* comparison before `completed` — is prompt-level only, and measurably fails 3/5 under load. Perception-limited verification (video) is a real ceiling.
- **Elite — 6/10.** Substrate: solid (spooling, timeout-preservation, mount isolation, budget honoring, graded-after-timeout). Traceability: strong (receipts, auto-persisted verifier bundles, proof board, provenance with tree hash). Deductions are all operational: broken suite at collection, everything-uncommitted, empty code_sha on the VM, ledger-vs-provenance model contradiction, ledger stale past session 4.

**Overall fit to vision: ~70%.** The architecture is the owner's vision, implemented honestly — I looked for harness-side completion theater, hidden fallbacks, and benchmark affordances the way an adversary would, and found none on the certified path. The missing 30% is split between one real capability gap (verifier falsification discipline, measurable, fixable in-vision) and an operational-discipline collapse that the vision's own governance section explicitly forbids. I am deliberately not scoring higher: a harness whose latest measured runs false-clean 3/5 and whose governing decision is uncommitted has not yet earned its own doctrine's standard, however good the code reads.

---

## F. Path to 100% on TerminalBench 2.0 — and the priority question

**Direct answer to the owner's question: for the failure classes actually observed, the Protean/minimal vision and 100% do not clash — they point at the same next work. The clash exists only at a margin you should accept.**

Where they align (and the evidence says this is most of the gap):
- **Decisive-evidence verification is both the largest measured score lever and squarely in-vision.** kv (trivial text comparison missed) and gcode (metadata accepted over geometry) are worth 2/5 of this board on their own, and the fix is generic structure, not task judgment.
- Step/budget handling (code-from-image A), protocol ergonomics, benchmark-native budget honoring — all substrate/protocol work the vision classifies as "the floor."

Where they genuinely tension — name it and reject it:
- **Task-family proof rules** ("for gcode, require geometry decoding"; "for proto tasks, diff field names") would convert these exact failures and are **forbidden** — they are the crutch, they die on the stronger-model test, and I recommend rejecting them even though they would demonstrably raise this board's score.
- **Verifier leniency/strictness tuning against pass rate** — same verdict, forbidden.
- **Perception ground truth** (video-processing): the verifier's judgment can only be as good as its own perception. Generic tooling can narrow it (frame-sweep via overlay + perceive loops), but at some point the verifier model *is* the ceiling. The vision says accept the honest loss; I agree. Budget for <100% on perception-adjudicated tasks until models improve — that is the vision working, not failing.

### The ordered plan (grounded in §D, each item tagged)

1. **Commit the world, in coherent slices** (vision-neutral, blocking everything): governing docs (CLAUDE.md/AGENTS.md/HARNESS_VISION.md) first — the canonical decision must exist at HEAD; then the EnvMap/truthfulness slices; then sentinel evidence + ledger notes; fix or delete `test_sentinel_proof_board.py` (it never ran); restore suite-green-at-HEAD. Revert the single-line prompt flattening. Update AETHER_NEXT_PROGRESS.md through the sentinel runs, including the failures.
2. **Resolve the sentinel model identity** (vision-positive: evidence truthfulness): check the Azure deployment behind `AZURE_OPENAI_GPT54_PRO_DEPLOYMENT`, correct the ledger notes, and make provenance record the resolved deployment/model name — not just the env-var name — so this class of contradiction cannot recur.
3. **Verifier falsification protocol** (vision-positive; the capability slice): extend the verifier runtime contract so a `completed` verdict must carry, per architect success criterion / minimum-completion-evidence item: (a) the requirement (quoted from packet), (b) the observed evidence satisfying it (quoted from its *own* inspection), (c) the falsification attempted — what observation would have contradicted it, and why it didn't. Enforce **structurally** (schema-required fields, refuse-and-retry like the existing gates at model_hooks.py:636-667) — the harness checks presence and provenance of the mapping, never its semantic truth. This passes the stronger-model test the same way receipts do: a stronger verifier fills it trivially and would never fight it; it is audit structure, not judgment. Also fix the two contract blemishes found in §D: architect doctrine must require *spec-anchored, method-independent* minimum evidence (ban "probe with the solver's stubs" / "spot-check around reported values" phrasing), and advertise the overlay as the mandated route when the decisive artifact exceeds direct-read spans.
4. **Score it with known-bads before trusting it** (mandated by this repo's own eval discipline): a small verifier-disagreement eval — wrong-field proto workspace, comment-vs-decoded-content workspace, off-by-frames workspace, plus the three real false-clean snapshots (already on disk under `snapshots/`) as fixtures. Prediction to record: kv-class and gcode-class convert to `needs_repair`/`incomplete_semantic_mismatch`; video-class may not. A falsification protocol that cannot fail a known-bad is theater — do not promote it without this board.
5. **Verifier verdict-taxonomy reconciliation** (small, vision-neutral): either advertise the 14 verdicts in the contract or cut back to the 5 advertised; keep `classify_verifier_outcome` receipts-only.
6. **Board at benchmark-native budgets, fixed committed SHA** (road item 8): 10–20 tasks across classes, task.toml budgets (not max-steps 30 — that manufactured both run-A incompletes), evidence dir exported, provenance with real SHA. This produces the first honest capability %, which does not exist yet — 5 tasks with an unresolved model identity is not it.
7. **Repo carve** (vision-positive, §C list): delete/archive the scrapheap, quarantine the ir-mode architect lineage into `reference_legacy/`, remove grader_hints vestiges + dead branches, finish size caps by real decomposition, commit aether2 reference state, then execute the `aether/` rename (road item 9) last.
8. **Then iterate per failure class from the board** — with the standing rule that every remaining non-pass gets the §D treatment: classified, evidenced, and answered with either generic mechanism or an accepted model-ceiling entry. The honest end-state of this plan is: every point below 100% has a written, evidence-backed reason that survives the stronger-model test. That — not a benchmark hack — is what "100% without compromising the vision" operationally means, and on current evidence nothing observed requires choosing between them except perception, where the vision correctly chooses itself.

---

## G. Verdict and recommendation

**Keep this codebase. Do not carve down or restart.** `aether_next_build/aether_next/` is a faithful, mostly-minimal implementation of the four-role vision whose remaining defects are enumerable and were found by its own instrumentation (the false-cleans were surfaced by the harness's alignment fields, not hidden by them — that is the system criticizing itself, which is exactly what you built it to do). The Aether-2 line is correctly dead as production; the vnext/backup trees are correctly dead as everything. The single next slice is **items 1+3+4 above as one unit: commit the tree honestly, add the falsification protocol, and prove it against known-bads including the three real false-clean workspaces already sitting in `snapshots/`.** I chose this over the two alternatives I seriously weighed — repo hygiene first (real, but it converts no failures and the scrapheap isn't corrupting decisions *this week*), and verifier-model-tier escalation first (cheap, but if the sentinel really ran PRO, escalation demonstrably does not buy falsification discipline by itself) — because it is the only slice that simultaneously repairs the evidence chain this project runs on and attacks the one failure class that currently costs the most score while being fully inside the vision. The biggest risk to this project is not the verifier; it is that its truth — decisions, code, and evidence — keeps living uncommitted in a working tree that one bad `git clean` erases.

---

### Appendix: key evidence index

- Tree-hash identity: `run_pilot._tree_hash(aether_next_build/aether_next)` → `d559c7dc4070…` == both runs' `run_provenance.code_tree_hash`.
- Suite: `python3.11 -m pytest tests -q` → collection error (`tests/test_sentinel_proof_board.py:5`); with `--ignore` → 338 passed, 12 skipped.
- False-clean verdicts: `vm_goal_runs/20260707T152214Z_sentinel/verifier_evidence/{video-processing/step_0006,gcode-to-text/step_0014}_solver_submit/parsed_verifier_result.json`; `…162100Z_sentinel_steps200/verifier_evidence/kv-store-grpc/step_0002_solver_submit/parsed_verifier_result.json`.
- Ground truths: `official_tasks/kv-store-grpc/instruction.md` ("value (int)"); `official_tasks/gcode-to-text/tests/test_outputs.py` (`flag{gc0d3_iz_ch4LLenGiNg}`); `official_tasks/video-processing/tests/test_outputs.py:97-107` (ranges 50-54/62-64, 219-223/231-234).
- Final wrong state: `…162100Z…/snapshots/kv-store-grpc/final/kv-store.proto` (`int32 val = 2` in SetValRequest).
- Runtime gates: [model_hooks.py:500-669](aether_next_build/aether_next/model_hooks.py:500). Packet leak assertion: [verifier_packets.py:206-228](aether_next_build/aether_next/verifier_packets.py:206). Verifier-gated completion: [kernel.py:327-343](aether_next_build/aether_next/kernel.py:327). Mount isolation + post-terminal grading: [docker_runner.py:263-275,390-426](aether_next_build/aether_next/runners/docker_runner.py:263).
- Size-cap violations: docker_runner 726, model_hooks 673, compiler 622, envmap_builder 599, runtime_ir 543, execution 512 (`find … | xargs wc -l`).
- Model-identity contradiction: `tracking/ledger/inbox/20260707T160900Z_sentinel_run.md` ("gpt-5.4-mini") vs `results.json` `model_params.solver_deploy_env: AZURE_OPENAI_GPT54_PRO_DEPLOYMENT`.

---

# Addendum (2026-07-08) — Phase-1 design review: three owner concerns, adjudicated

The owner raised three concerns against §F item 3 before execution. Each was re-audited against primary evidence, not against the report's own framing. Decisions below supersede the corresponding parts of §F. This is my call as principal architect; reasoning is recorded so it can be attacked later.

## Concern 1 — does a falsification-protocol gate cross into "harness dictates how the model must think"?

**Adjudication: the concern is partially valid against my original wording; the design is revised, not dropped.**

There are three distinct enforcement categories, and the vision treats them very differently:

1. **Act-occurred gates** — "an inspection must have happened before completion is accepted." Facts about the world, checkable via receipts. This is the existing gate ([model_hooks.py:534-567](aether_next_build/aether_next/model_hooks.py:534)) and is uncontroversially in the invariant core (verification-must-happen).
2. **Output-protocol shape** — required fields per verdict. This category *already exists and is already accepted*: `parse_model_verifier_result` rejects `completed` without summary/evidence, `needs_repair` without findings, `uncertain_missing_evidence` without requests ([verifier.py:160-185](aether_next_build/aether_next/verifier.py:160)), and `finding_shape` prescribes finding structure. Nobody considers a tool-call schema "dictating thought"; it is protocol.
3. **Content-adequacy judgment** — the harness evaluating whether the reasoning inside those fields is *good* (keyword checks, per-evidence-class method requirements, coverage matching of record entries onto config items). **This is the line. It is never crossed.**

My original §F wording ("falsification attempted — what observation would have contradicted it, and why it didn't") drifted toward category 3 by implying the harness cares what the falsification *is*. Revised design, pinned to categories 1+2 only:

- A `completed` verdict must carry a `completion_evidence` array with ≥1 entry; each entry has non-empty `requirement`, non-empty `observed`, non-empty `falsification_check`, and `inspection_refs` that **resolve to inspections actually performed in this verification round** (referential integrity — a category-1 fact, checked against the round's inspection records, content-blind).
- The harness checks **presence, non-emptiness, and reference resolution. Nothing else.** No keyword matching, no adequacy scoring, no per-class method rules in code, no coverage mapping against the architect's lists (that would require semantic matching — excluded by design).
- Failure mode mirrors the existing gates: one corrective protocol instruction, then refuse-and-convert to `uncertain_missing_evidence` with an explicit finding — a protocol event, never a harness verdict on the task.

The line, stated precisely: **the harness may require that authority-bearing verdicts be accompanied by (a) acts that happened and (b) a structured record whose references resolve to those acts; it may never evaluate whether the reasoning in the record is good.** Stronger-model test: a stronger verifier fills the record trivially and never fights it — it degrades into pure audit structure, the same family as receipts and the evidence ledger, which the vision places in the invariant core. A weak verifier can fill it with boilerplate; the gate does not manufacture judgment (so it is not compensation) — it makes ignoring one's own brief *visible and auditable*, which is what an evidence ledger is for.

## Concern 2 — architect-led instead of harness-led?

**Adjudication: not either/or — both, with the architect primary. Prompt-only is empirically insufficient; this was already tested.**

The architect-led route is not hypothetical: the sentinel *was* its test. All three false-clean configs contained specific, correct, plain-language warnings naming the exact failure that then occurred (§D2–D4), including one the verifier ignored while using the word "decisive" about the disqualified evidence class. Violations happened at 0.89–0.97 confidence under a (probably) pro-tier verifier. A "stronger prompt" is a bet that more of the same input fixes a failure that already survived a good version of that input, three times out of three opportunities. The mechanism of failure is general LLM behavior: unstructured obligations decay under confident execution; **schema-bound obligations get discharged** (the same model that skipped its falsification brief reliably produced verdict/summary/findings, because the schema demands them). That is the concrete reason prompt-only isn't enough — evidence, not taste.

But the ownership boundary stands, and it answers the design question:

- **Architect (primary)** — owns *what must be proven*. Its doctrine needs repair regardless: two of three sentinel configs embedded self-confirming `minimum_completion_evidence` ("a live probe … using a client built from the generated stubs"; "a separate frame spot-check **around the reported** takeoff and landing frames"). The workbench architect prompt gains the norm: minimum evidence must be spec-anchored and method-independent; never anchored to solver-produced artifacts or solver-reported values.
- **Harness (secondary, thin)** — enforces *that the verifier's completion engages the architect's contract*, via the content-blind record above. The harness authors no obligations; it makes the architect's obligations undroppable at the protocol layer. Architect = what; verifier = whether; harness = that-the-answer-engages-the-question. No shared ownership.

**Ordering: they ship together, and the order inside the slice matters.** The backstop without the doctrine fix faithfully discharges self-confirming lists (kv's stub-probe item would have been "discharged" by exactly the false-clean evidence that fooled it). The doctrine fix without the backstop is the configuration that already failed. The known-bad eval judges the pair; predictions recorded below.

## Concern 3 — video-processing was mischaracterized. Confirmed; retraction.

Re-read from source, as directed:

- `official_tasks/video-processing/solution/solve.sh`: the reference solution is **pure deterministic computer vision** — `cv2.bgsegm.createBackgroundSubtractorMOG()` background subtraction, Gaussian blur + morphological open/close, bottom-slice foot tracking, jump = the movement event with maximum step distance. No vision-model perception exists anywhere in the intended solve path, and the task's library restriction (`toml`, `cv2`, `numpy` only) does not admit one.
- Grader (`tests/test_outputs.py`): checks the two frame numbers against inclusive ranges on both the example and a held-out video. Frame numbers are **machine-re-derivable values**.
- Failed run (`vm_goal_runs/20260707T152214Z_sentinel/`): the verifier had `overlay_run_command` in a workspace copy sharing the solver container's toolchain (cv2 available) — a deterministic, independent derivation route. It used none of it: one `perceive_artifact` of `/app/jump_probe.jpg`, a **solver-authored** contact sheet built around the solver's own guessed frames, whose extraction was even labeled `model_transcription_not_ground_truth` by the runtime — a label the contract already tells the verifier to audit against independent evidence.

**This is the same self-confirmation class as kv-store-grpc and gcode-to-text, not a perception ceiling.** My report's "genuine model-capability ceiling / accept the loss" framing (§D2, §E, §F) is retracted for this failure. The residual model-capability truth is narrower: *achieving a pass* still requires someone to write a correct CV detector (expert estimate 400 min), and an independent verifier derivation is bounded by the same model class's CV ability. So the ceiling applies to converting video into a *pass*, not to refusing the false clean.

Fold-in, kept on the right side of the Concern-1 line: the **independence norm** enters as uniform contract doctrine and architect doctrine — "when a claimed value is machine-re-derivable (counts, frame indices, field names, hashes, parsed values), decisive evidence must come from your own independent derivation (overlay execution, probes, your own perception of task inputs), not from inspection of solver-produced artifacts" — **not** as a harness-enforced rule, because deciding which claims are machine-re-derivable is semantic judgment the harness must not perform. The `completion_evidence` record makes compliance with the norm auditable per run.

## Revised predictions (recorded before the eval, per experiment discipline)

One generic mechanism (doctrine + record), three sentinel false-cleans:

| Case | Converts to honest non-completion | Converts to official PASS on rerun |
|---|---|---|
| kv-store-grpc (field-name mismatch) | HIGH | HIGH (one-line fix once the verifier surfaces it) |
| gcode-to-text (metadata vs toolpath) | HIGH | MEDIUM (solver must actually decode; feasible in-container) |
| video-processing (self-confirming perception) | MEDIUM-HIGH | LOW-MEDIUM (detector quality is genuinely model-bound) |

Alignment conversion ≠ score by itself: false-clean → honest-fail restores the feedback loop (verifier findings → solver repair), which is the actual score path. If the known-bad eval shows the record being filled with boilerplate discharges of self-confirming evidence, the prediction is FAILED and gets recorded as such — not reinterpreted.
