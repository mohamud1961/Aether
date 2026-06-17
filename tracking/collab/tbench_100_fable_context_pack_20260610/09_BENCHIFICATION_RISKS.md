# 09 — Benchification Risks

## Definition

**Benchification**: building harness behavior that improves scores on
*this specific* eval suite (or even on TB2.0's specific public/leaked task
set) by exploiting its particular structure, names, fixtures, or grader
quirks — rather than building generalizable agent capability that would
transfer to held-out tasks of the same *type*.

The project's central design philosophy, stated repeatedly across
`AGENTS.md` and the variant backlog: **"Model decides strategy. Harness
preserves truth."** The harness's job is to give the model accurate
information about the world (file contents, command results, service
state, success criteria) and to verify claims against reality — not to
encode task-specific shortcuts, answer lookups, or grader-mimicking logic.

Fable may challenge or refine this principle if evidence supports a better
formulation, but should not discard it without a concrete replacement.

## What's allowed

- Generic mechanisms that improve how the harness presents information,
  verifies claims, or recovers from errors, **regardless of task content**:
  cwd/path normalization, service-readiness receipts, context compaction,
  recovery-fingerprint extraction, tool-contract repair that works for any
  tool/argument shape.
- Mechanisms derived from **abstracted** failure patterns — e.g., "agents
  often pick the wrong file when multiple similarly-named files exist" is a
  generic pattern; a fix for it (disambiguation prompt, decoy-resistant
  selection) is allowed even if it was *discovered* by looking at a specific
  eval task, as long as the fix doesn't reference that task's specific
  filenames/values.
- Custom evals that **abstract** a public benchmark failure family — change
  names, values, layouts, distractors, fixtures while preserving causal
  structure (per AGENTS.md's "benchmark-derived custom evals must abstract
  the failure family, not copy the public row").
- Truthful, generic grading that parses the **task's own** test/verifier
  files (e.g. `phase65_measurement_grading.py`'s approach of `ast`-parsing
  `tests/test_outputs.py` for a `SOLUTION` constant) — this is fine because
  it works for any task that ships such a file, not just one task.

## What's forbidden

- Hardcoding specific tool names, argument values, file paths, or expected
  outputs from TB2.0 tasks (official or homolog) into harness/runner code.
  **Combined Guard V1.5's `lookup_customer_order: include_history=True`
  injection is a borderline-violating example** — it's hardcoded to one
  tool name from one eval task family. Even though it was built for a
  *custom* eval (not an official TB2.0 task), the pattern (hardcode a
  specific tool/arg fix) would be a clear violation if applied to an
  official task.
- Any mechanism that reads or depends on hidden grader/verifier files,
  `expected_*`/`ground_truth_*` fields, or other oracle information at
  *runtime* (during the agent's execution). Note:
  `kernel_layer2_audit.py`'s `_clean_hidden_refs()` actively strips such
  keys — this is the *correct* direction; any new mechanism should be
  checked against this same filter.
- Memorizing or special-casing behavior for specific official TB2.0 task
  IDs (`extract-moves-from-video`, `headless-terminal`,
  `install-windows-3.11`, `mailman` — the 4 official tasks present in
  `official_tasks/`). These exist for **calibration/audit**, per AGENTS.md
  ("public benchmarks are calibration and audit surfaces, not the inner
  optimization loop") — not for tuning.
- "Verifier-as-oracle" loops where the harness iterates against the
  *hidden* verifier's output until it passes (as opposed to the model's own
  declared, generic success criteria via `kernel_success_contract.py`).
- Native-runner overfitting: tuning `benchmark_adapter_terminalbench_native.py`
  or `certified_sandbox.py` to the specific quirks of the 4 local official
  tasks rather than the general TB2.0/Harbor contract
  (`EXPECTED_REMOTE_FRAGMENT = "harbor-framework/terminal-bench"` exists
  precisely to keep this honest — verify it's actually enforced).
- Task-family "playbooks" — e.g., a lookup table mapping task-name patterns
  to pre-baked action sequences. None currently exist, but the
  "Stem Agents" / static-system-prompt idea (Antigravity, 2026-05-30) should
  be checked it doesn't drift toward this.

## Specific risks identified in this codebase

1. **Combined Guard V1.5** (`blocks/tools/result_attribution_guard_common.py`)
   — `_repair_sentinel_contract()` hardcodes `lookup_customer_order` and
   `include_history`. Even setting aside its sentinel regression (`07`#6),
   this is the kind of mechanism that should be **generalized or killed**
   before any reuse: a generic version would detect "tool X has a
   commonly-required-but-often-omitted argument Y" from the tool's own
   schema/contract, not from a hardcoded tool name.
2. **GPT-5.5 Pro synthesis context dumps**
   (`tracking/collab/gpt55pro_best_harness_synthesis/INPUT_CONTEXT_AND_PROMPT*.md`,
   1.5-3.16MB) — these embed "native benchmark-only result rows" and
   "Vix raw trajectory excerpts." If future mechanism design is derived
   from reading these dumps, ensure any resulting mechanism is described
   generically (e.g., "Stem Agents: static system prompt + session
   forking + comment-stripping") and not as "do what Vix did on task X."
3. **"Stem Agent" / VFS minification** (comment-stripping) — generally
   fine as a context-reduction technique, but if comment content is ever
   load-bearing for a specific task's verification (e.g. a task that asks
   the agent to read/preserve comments), a blanket strip could cause
   task-specific failures that get "fixed" by special-casing — watch for
   this drift.
4. **`terminalbench_verifier_repair` eval being non-discriminating**
   (`07`#11) — there's a temptation to "fix" this by tuning the eval until
   it produces the desired pass/fail split for a specific mechanism, rather
   than independently strengthening its pressure. Any eval-strengthening
   work should be done *before* and *independent of* the mechanism it will
   be used to evaluate.
5. **`tool_result_attribution` eval leakage** (`07`#12) — if "fixed" by
   adjusting the harness to work around a leaky fixture rather than fixing
   the fixture, the resulting mechanism may be tuned to the leak.

## Rules for honest task success (synthesized for Fable)

1. Every new mechanism must have a plausible one-sentence description that
   doesn't name a specific tool, file, or task ID.
2. Every new mechanism must be tested against held-out variation (different
   filenames/tool names/task instances of the same *family*) before
   promotion — not just the exact eval row it was designed against.
3. No runtime code path may read fields named `expected_*`, `*_hidden*`,
   `*_secret*`, `*ground_truth*`, or grader/verifier source files —
   `_clean_hidden_refs()` is the existing pattern; extend its key-list as
   needed rather than bypassing it.
4. Official TB2.0 tasks (`official_tasks/`) are for periodic calibration
   runs only — never for iterative tuning. If a mechanism is tuned using
   official-task feedback, it must be re-validated on custom/homolog evals
   before being trusted.
5. When a mechanism's win depends on a specific named entity (tool name,
   file name, process command), treat that as a code smell requiring either
   generalization (derive the same fix from the tool's schema/contract
   generically) or rejection.
