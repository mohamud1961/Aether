# RAW_LEDGER_UPDATE: AHP Prompt Layering Fix + Working-Tree Manifest

**Date:** 2026-06-21
**Type:** implementation + audit artifact
**Status:** COMPLETE

## Task 1: AHP Prompt Layering Fix (flag-ON path only)

### Problem
AHP startup concatenated the model-authored task block INTO the system prompt
(`system_prompt = kernel + "\n\n" + task_block`). This made the system prompt
vary per task, breaking cacheability and violating the design contract that the
system prompt = the stable invariant kernel only.

### Fix
- `harness/aether2/runtime/adaptive_context.py`:
  - `apply_adaptation_contract()`: system_prompt now always = base_system_prompt
    (the kernel). Task block is NO LONGER concatenated into system_prompt.
  - `_build_extra_prefix_messages()`: now accepts `task_block` param and builds
    the frozen context pack with: (1) task block tagged `[ahp_task_block]`,
    (2) profile summary `[ahp_profile_summary]` with watchpoints/do_not_assume/
    selected-tools, (3) initial plan CONTENT (frozen; status renders in tail).
  - Only the `use_full_generated_prompt=True` ablation knob can replace the
    system prompt (not the default path).

- `harness/aether2/control/ahp_preflight.py`:
  - Replaced `task_block_after_kernel` / `task_block_appended` checks with
    `system_prompt_is_kernel_only` and `task_block_in_context_pack`.
  - Added `task_block_first_in_pack`, `plan_content_frozen_in_pack`,
    `plan_status_renders_separately` checks.
  - Preflight now 45/45 (was 42/42).

### Invariant Proof
- **Flag-OFF byte-identity**: PROVEN. Baseline prefix digest =
  `e2c6c9c9d897bcbc...` matches flag-off prefix digest exactly.
  `_baseline_run_config()` produces: system_prompt == SYSTEM_PROMPT,
  extra_prefix_messages == [], task_block == "".
- **Flag-ON structure**: system_prompt == SYSTEM_PROMPT (kernel only, 5547 chars);
  task block delivered via `extra_prefix_messages[0]` with `[ahp_task_block]` tag;
  plan content frozen in `extra_prefix_messages[2]`; plan status renders only via
  `_render_initial_plan_checklist()` (dynamic tail path).
- **pytest**: 151/151 passed.
- **AHP preflight**: 45/45 passed.
- **Genericity check**: clean.
- **No unrelated files touched.**

### Files Changed (Task 1)
- `harness/aether2/runtime/adaptive_context.py` (437 LOC)
- `harness/aether2/control/ahp_preflight.py` (582 LOC — was already >500 pre-change)

## Task 2: Working-Tree Manifest

### Output
`tracking/collab/working_tree_manifest_20260621.md`

Groups ~168 changed/untracked entries into 12 workstreams:
1. AHP variant (16 files, COHERENT/COMPLETE)
2. 14-row custom board build (~55 files, COHERENT/PARTIAL)
3. Service-lifecycle fix (~19 files, COHERENT/COMPLETE)
4. BFCL native (~10 files, PARTIAL/UNSAFE — quarantined)
5. Stage 0 launch/path fix (1 shared file, COHERENT/COMPLETE)
6. Compaction sentinel (1 file, COHERENT/COMPLETE)
7. Harness core repairs (~14 files, COHERENT/COMPLETE)
8. Governance docs (2 files, COHERENT/COMPLETE)
9. Benchmark adapters non-BFCL (~18 files, COHERENT/PARTIAL)
10. Environment bootstrap pack (~6 files, COHERENT/PARTIAL)
11. Pre-existing/unattributed (~6 files)
12. Tracking/ledger data (tree)

7 files flagged with uncertain attribution (multi-workstream contributors).

## Evidence
- Preflight output: 45/45 PASS
- pytest: 151/151 passed
- Genericity check: clean
- Flag-off digest proof: identical
- Manifest: tracking/collab/working_tree_manifest_20260621.md
- No processes left running
- No commits made
- No task solving performed
