# Public Eval Pack Handoff

- Status: COMPLETE
- Source thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Target thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Date: `2026-06-15`

## Files Changed

- `eval_suite/custom/public_manifest_repair_smoke/README.md`
- `eval_suite/custom/public_manifest_repair_smoke/task_pack.json`
- `eval_suite/custom/public_manifest_repair_smoke/grader.py`
- `eval_suite/custom/public_manifest_repair_smoke/fixture/workspace/release/manifest.json`
- `eval_suite/custom/public_manifest_repair_smoke/fixture/workspace/release/summary.txt`
- `eval_suite/custom/public_manifest_repair_smoke/fixture/workspace/release/checksum.txt`
- `eval_suite/custom/public_manifest_repair_smoke/fixture/workspace/notes/obsolete.md`
- `eval_suite/custom/public_manifest_repair_smoke/fixture/workspace/tmp/cache.txt`
- `eval_suite/custom/public_manifest_repair_smoke/fixture/reference/manifest.json`
- `eval_suite/custom/public_manifest_repair_smoke/fixture/reference/summary.txt`
- `eval_suite/custom/public_manifest_repair_smoke/fixture/reference/checksum.txt`
- `eval_suite/boards/public_manifest_repair_smoke_v1.json`
- `eval_suite/scoreboards/public_manifest_repair_smoke_v1.example.scoreboard.json`
- `tools/run_public_manifest_repair_smoke.py`
- `tests/test_public_manifest_repair_smoke.py`
- `eval_suite/README.md`
- `eval_suite/custom/README.md`
- `eval_suite/boards/README.md`
- `eval_suite/graders/README.md`
- `eval_suite/scoreboards/README.md`
- `docs/architecture/public-architecture.md`

## Result

- COMPLETE
- Delivered one public-safe custom eval-pack slice under `eval_suite/custom/`.
- The pack is original, synthetic, deterministic, locally runnable, and does not require credentials or model calls.
- The slice preserves harness behavior and does not modify Aether runtime/control/tool logic.

## Task-Pack Design

- Family: `public_manifest_repair_smoke`.
- Task type: filesystem/verifier repair on a messy synthetic release workspace.
- Workspace shape: candidate files live under `workspace/release/`; decoy files live under `workspace/notes/` and `workspace/tmp/`.
- Reference shape: canonical truth lives under `reference/`.
- Grader behavior: compare the normalized manifest, the summary sentence, and the manifest-derived checksum deterministically.
- Board behavior: the board points at the task pack, grader, fixture root, and smoke runner.
- Scoreboard behavior: the example scoreboard contains two validated rows, one pass and one fail, with an explicit `example_only` label.

## Why It Is Public-Safe

- It is wholly synthetic and locally authored.
- It does not copy eval names, private fixtures, hidden grader logic, or raw trace material.
- It does not encode private data, credentials, or external service dependencies.
- The example scoreboard is clearly labeled as smoke/example output, not eval evidence.
- The smoke script runs only a deterministic local grader and writes portable result rows.

## Validation

- `python3 -m pytest tests/test_public_manifest_repair_smoke.py -q -p no:cacheprovider`
- Result: `5 passed in 0.03s`
- `python3 -m py_compile eval_suite/custom/public_manifest_repair_smoke/grader.py tools/run_public_manifest_repair_smoke.py tests/test_public_manifest_repair_smoke.py`
- Result: passed
- `python3 tools/aether2_genericity_check.py`
- Result: passed
- `python3 tools/run_public_manifest_repair_smoke.py --output-root /tmp/public_manifest_repair_smoke_validation`
- Result: passed and wrote `/tmp/public_manifest_repair_smoke_validation/public_manifest_repair_smoke_example.json`
- `git diff --check`
- Result: passed

## Claims Excluded Or Qualified

- No claim that this pack is eval evidence.
- No claim that the score is representative of external model performance.
- No claim that the repository now has a full eval suite; this is one public smoke slice.
- No claim of production readiness or certified run coverage.

## Adversarial Review

### Eval Engineer View

- Finding: the smoke runner initially depended on importing `runner` without bootstrapping the repo root.
- Repair: added a repo-root `sys.path` shim before the harness imports.

### Hiring Reviewer View

- Finding: the task prompt and example paths needed to read as a real public slice, not a eval stub.
- Repair: added a concrete custom pack, deterministic grader, board manifest, example scoreboard, and discoverability docs.

### Maintainer View

- Finding: the first pass test setup did not copy the fail-side reference fixture the same way the runner does.
- Repair: aligned the test fixture copy behavior with the smoke runner and tightened the assertions to match repo-relative board refs.

## Remaining Publication Gaps

1. Add a second public custom pack to show a different eval family, ideally structured extraction or config normalization.
2. Add shared schema docs for task pack, board, grader, and result-row shapes if the public eval surface expands.
3. Expand `eval_suite/fixtures/` and `eval_suite/sentinels/` with another smoke example once the next pack lands.

## Exact Next Dependency-Ready Publication Slice

- Publish one additional public-safe custom pack under `eval_suite/custom/` with its own board and example scoreboard, using a different failure family than manifest repair.

## External-State Confirmation

- No branch, worktree, commit, push, VM, server, or credential change was introduced for this slice.
- The direct smoke run used only `/tmp/public_manifest_repair_smoke_validation` and left no persistent process running.

## RAW_LEDGER_UPDATE

- Persisted: yes
- Private raw historian input path: `tracking/ledger/inbox/2026-06-15/194155_public-repository-worker-7_first-concrete-public-eval-pack-slice_422c71ef6d.md`

## Thread Send

- Target thread ID: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Send result: success (`codex_app.send_message_to_thread`)
