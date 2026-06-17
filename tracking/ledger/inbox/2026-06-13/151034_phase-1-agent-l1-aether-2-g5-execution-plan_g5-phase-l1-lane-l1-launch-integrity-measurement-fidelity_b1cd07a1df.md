# Raw Ledger Update

- recorded_at_utc: 2026-06-13T15:10:34.955901+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Phase-1 agent (L1, Aether-2 G5 execution plan)
- task: G5 Phase L1 (lane L1: launch integrity + measurement fidelity)
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: b1cd07a1df5aa1419cfcd9664a5a05efb5b25d43318aca88d8586185fbbdc7e3
- commit_message: "Add L1 launch-integrity sentinel test, hardened tournament launcher, and VM patch spec for F1 import-path fix"
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-13/151034_phase-1-agent-l1-aether-2-g5-execution-plan_g5-phase-l1-lane-l1-launch-integrity-measurement-fidelity_b1cd07a1df.md

```text
RAW_LEDGER_UPDATE
- actor: Phase-1 agent (L1, Aether-2 G5 execution plan)
- task: G5 Phase L1 (lane L1: launch integrity + measurement fidelity)
- event_type: implementation
- summary: Implemented all locally-doable L1 deliverables for the F1 launch-collapse repair (457/482 "ModuleNotFoundError: No module named 'runner'" crashes in the frozen G4 n=2 tournament). Added a generic regression sentinel test, a hardened tournament launcher script with preflight import check + fail-fast + invalid_launch rows, and a ready-to-apply VM patch spec + L1-C measurement-fidelity checklist + VM-execution handoff. No runner/aether2/*.py behavior changed.
- observations: |
    1. tests/test_aether2_entrypoint_import_hygiene.py (new) glob-discovers tools/run_aether2_*.py and any tools/run_*.py with a top-level `from runner`/`import runner`, launches each with `--help` from a foreign tempdir cwd with PYTHONPATH stripped, and asserts the combined stdout+stderr never matches `ModuleNotFoundError: No module named 'runner'`. It does not assert on exit code (per spec). 5 tests pass (4 parametrized over discovered entrypoints incl. run_aether2_g2.py + 1 discovery sanity check).
    2. python3 tools/aether2_genericity_check.py exits 0 (no output, rc=0).
    3. python3 -m pytest tests/test_aether2_entrypoint_import_hygiene.py tests/test_aether2_genericity.py -q -> "8 passed in 17.93s".
    4. tools/run_aether2_g3_official.py does NOT exist in this local repo (confirmed via find); only the frozen broken copy under tracking/collab/vm_pulls/.../source_snapshot/tools/run_aether2_g3_official.py exists, confirmed missing the sys.path bootstrap at lines 30-32 vs tools/run_aether2_g2.py:34-39 (and the same pattern in run_benchmark_adapter_smoke.py / run_benchmark_adapter_bfcl_native_smoke.py / run_final_harness_eval_suite_baseline.py, all of which already have REPO_ROOT + sys.path.insert before `from runner...`).
    5. scripts/run_aether2_tournament.sh (new, chmod +x) supports --help and --dry-run; --dry-run with no --task-ids-file does preflight-only and exits 0; --dry-run with --task-ids-file prints the planned timeout/python3 invocations per task without executing; a real (non-dry) invocation against this repo passes the preflight `python3 -c "import runner.aether2.bridge_harbor"` check and then correctly errors (exit 64, clear message pointing at L1_vm_patch.md) because tools/run_aether2_g3_official.py is VM-only and absent locally.
    6. tracking/collab/aether2_g5_run_analysis_20260613/L1_vm_patch.md (new) contains: (a) the exact 2-line+3-noqa unified diff for tools/run_aether2_g3_official.py matching run_aether2_g2.py's bootstrap pattern; (b) launcher usage docs; (c) the L1-C checklist (test-mount mirroring for break-filter-js-from-html, hermetic grader toolchain for broken-python/broken-networking exit-127, 127/137/400 -> invalid_run/invalid_environment row_status classification, phase-boundary row.json writes for build-initramfs-qemu-style kills); (d) a staged VM-execution handoff (Step 0 apply+verify, Step 1 micro-smoke 3 tasks, Step 2 targeted 14-task set) with explicit success checks including reach-grader >=95% and the 5 known passes (acl-permissions-inheritance, analyze-access-logs, assign-seats, attention-mil, build-pmars).
    7. Host fork pressure (`fork: Resource temporarily unavailable` from /opt/homebrew/bin/brew and zprofile) was hit twice during shell validation; both times a short retry succeeded. tests/conftest.py's spawn_with_retry (pre-existing, untouched) is used inside the new test to harden subprocess.Popen against the same class of host-load issue.
- inference: The F1 root cause and fix are exactly as diagnosed in failure_taxonomy.md and G5_EXECUTION_PLAN.md L1-A -- a single missing sys.path bootstrap in a VM-only file, with a verified-correct canonical pattern already present 4x elsewhere in tools/. The local repo cannot reproduce or apply that specific file edit (file absent), so L1-A is delivered as a precise diff spec rather than an Edit. All other L1 deliverables (sentinel test, launcher, L1-C checklist, handoff) are fully implementable and validated locally.
- evidence_paths: |
    tests/test_aether2_entrypoint_import_hygiene.py
    scripts/run_aether2_tournament.sh
    tracking/collab/aether2_g5_run_analysis_20260613/L1_vm_patch.md
    tools/run_aether2_g2.py (lines 34-39, canonical bootstrap pattern, unmodified)
    tracking/collab/vm_pulls/tracking/collab/aether2_g5_failure_analysis_clean_20260613T121431Z/source_snapshot/tools/run_aether2_g3_official.py (lines 15-32, confirmed missing bootstrap, read-only)
- affected_components: tests/ (new sentinel), scripts/ (new launcher), tracking/collab/aether2_g5_run_analysis_20260613/ (new patch spec doc). No runner/aether2/*.py changed.
- decision_change: None -- this is the planned L1 lane execution per G5_EXECUTION_PLAN.md. L2-L6 not started, as scoped.
- unresolved_questions: |
    Whether L1-A alone (without L1-C) is sufficient to flip break-filter-js-from-html to pass is unresolved -- L1_vm_patch.md frames L1-C item 1 (test-mount mirroring) as the likely additional fix, per the plan's own "L1-C likely flips break-filter" framing. The exact on-VM output_root/row.json path produced by tools/run_aether2_g3_official.py (output_root/<timestamp>/<task_id>/row.json per the frozen snapshot) is assumed stable; scripts/run_aether2_tournament.sh's row.json discovery (find ... -path "*/<task_id>/row.json") depends on that assumption holding after the L1-A/L1-C edits. None of L1-A, L1-B, L1-C, or the VM-execution handoff has been run on the VM -- this sandbox cannot reach the Azure control plane, Docker, or the VM, so no reach-grader-rate or pass-rate numbers were produced or could be produced.
- confidence: high (diagnosis + local implementation + local test results); VM-side application and validation is unverified by construction (out of reach).
- commit_message: "Add L1 launch-integrity sentinel test, hardened tournament launcher, and VM patch spec for F1 import-path fix"
```
