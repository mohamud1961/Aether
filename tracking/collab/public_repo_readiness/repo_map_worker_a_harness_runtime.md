# Repo Mapping Worker A: harness/runtime/tools/tests inventory

## Executive Summary

`runner/aether2/` is currently a mixed runtime/control/trace package, not a cleanly layered harness subtree. The safest public split is:

- keep `runner.aether2` as a thin compatibility shim;
- move the real implementation to `harness/aether2/{runtime,control,verification,env,traces,monitoring,tools}`;
- keep the current top-level `tools/*.py` as CLI shims until callers are migrated;
- archive the `packet07_*` and `successor_*` families instead of promoting them into the new public core.

The highest-risk breakpoints are private helper imports from `runner.aether2.bridge_harbor` into `tools/run_aether2_g2.py` and `tools/run_aether2_g3_official.py`, plus the broad test surface that imports `runner.aether2.*` directly. There are also several test-imported `tools.*` modules that are not present in this checkout, which reads as stale/missing test debt rather than a clean migration target.

`runner/README.md` is also slightly stale: it references `docs/current_surface_map.md` and `docs/deprecation_map.md`, but those files are absent from this tree.

## Inventory

### Aether-2 package

| Path | Current role | Recommended classification | Recommended target path | Notes |
|---|---|---|---|---|
| `runner/aether2/__init__.py` | Re-export surface for the whole package | public compatibility shim | `runner/aether2/__init__.py` stays, forwards to `harness/aether2` | Keep stable import path for incremental migration |
| `runner/aether2/bridge_harbor.py` | Task mounting, Harbor runtime wiring, run manifest assembly | move to harness/aether2/runtime | `harness/aether2/runtime/bridge_harbor.py` | Breaks `tools/run_aether2_g2.py`, `tools/run_aether2_g3_official.py` unless shimmed |
| `runner/aether2/cleanup_accounting.py` | Cleanup attribution bookkeeping for owned resources | move to harness/aether2/monitoring | `harness/aether2/monitoring/cleanup_accounting.py` | Monitoring/cleanup accounting, not core execution |
| `runner/aether2/compactor.py` | Context rebasing and fact-ledger handoff | move to harness/aether2/control | `harness/aether2/control/compactor.py` | Control-plane logic |
| `runner/aether2/context.py` | Cached prefix and transcript management | move to harness/aether2/runtime | `harness/aether2/runtime/context.py` | Core prompt/cache state |
| `runner/aether2/delta.py` | Workspace snapshots, diffs, evidence ledger | move to harness/aether2/traces | `harness/aether2/traces/delta.py` | Trace/evidence substrate |
| `runner/aether2/envelope.py` | Typed observation envelopes and truncation digests | move to harness/aether2/traces | `harness/aether2/traces/envelope.py` | Trace capture plus monitoring metadata |
| `runner/aether2/escalation.py` | Route escalation decision policy | move to harness/aether2/control | `harness/aether2/control/escalation.py` | Policy, not runtime plumbing |
| `runner/aether2/executor.py` | Workspace-scoped foreground execution and container backing | move to harness/aether2/runtime | `harness/aether2/runtime/executor.py` | Runtime core |
| `runner/aether2/jobs.py` | Detached job registry and liveness checks | move to harness/aether2/runtime | `harness/aether2/runtime/jobs.py` | Runtime core |
| `runner/aether2/loop.py` | Main Aether-2 agent loop, tool dispatch, verifier gating, completion policy | move to harness/aether2/control | `harness/aether2/control/loop.py` | The orchestration brain; should not sit in runtime |
| `runner/aether2/metrics.py` | Scorecard aggregation and action breakdowns | move to harness/aether2/monitoring | `harness/aether2/monitoring/metrics.py` | Monitoring/scorekeeping |
| `runner/aether2/mirror.py` | Semantic mirror / observation tracker | move to harness/aether2/traces | `harness/aether2/traces/mirror.py` | Trace classification and mirror notes |
| `runner/aether2/model_client.py` | Provider route wrapper and normalized retries | move to harness/aether2/runtime | `harness/aether2/runtime/model_client.py` | Runtime-facing client boundary |
| `runner/aether2/orientation.py` | Environment probes and contract snapshot | move to harness/aether2/env | `harness/aether2/env/orientation.py` | Environment contract belongs here |
| `runner/aether2/prompts.py` | Doctrine, system prompt, handoff template | move to harness/aether2/control | `harness/aether2/control/prompts.py` | Prompt policy is control-plane content |
| `runner/aether2/receipts.py` | Redacted receipt capture and normalization | move to harness/aether2/traces | `harness/aether2/traces/receipts.py` | Trace artifact handling |
| `runner/aether2/sessions.py` | tmux-backed session registry | move to harness/aether2/runtime | `harness/aether2/runtime/sessions.py` | Runtime execution support |
| `runner/aether2/tools.py` | Generic tool schemas and dispatch helpers | move to harness/aether2/tools | `harness/aether2/tools/tools.py` | Keep schema names stable for compatibility |
| `runner/aether2/verify.py` | Fresh-context verification and replay checks | move to harness/aether2/verification | `harness/aether2/verification/verify.py` | Verification boundary, not runtime |

### Top-level `tools/`

| Path | Current role | Recommended classification | Recommended target path | Notes |
|---|---|---|---|---|
| `tools/aether2_decision_trace.py` | Trace reconstruction and receipt bundling CLI | move to harness/aether2/traces | `harness/aether2/traces/decision_trace.py` | Analysis-only trace tooling |
| `tools/aether2_fake_progress_homologs.py` | Synthetic homolog manifest/fixture/grade helpers | move to harness/tools | `harness/tools/aether2_fake_progress_homologs.py` | Eval-generation tooling, not runtime |
| `tools/aether2_genericity_check.py` | Mechanical genericity gate for the Aether-2 line | move to harness/tools | `harness/tools/aether2_genericity_check.py` | Policy checker used by tests and CI |
| `tools/aether2_grader_isolation.py` | Official-test mount and grader-isolation contract helpers | move to harness/aether2/env | `harness/aether2/env/grader_isolation.py` | Environment contract rather than runtime |
| `tools/aether2_targeted_board.py` | Targeted-board manifest and scheduler validator | move to harness/tools | `harness/tools/aether2_targeted_board.py` | Board/eval governance tooling |
| `tools/render_final_harness_scoreboard.py` | Deterministic scoreboard rendering | move to harness/tools | `harness/tools/render_final_harness_scoreboard.py` | Shared eval reporting utility |
| `tools/run_aether2_fake_progress_runner.py` | Reserved future runner entrypoint | public compatibility shim | keep current file, or wrap a future `harness/tools` implementation | Explicit placeholder, not executable today |
| `tools/run_aether2_g2.py` | G2 homolog runner | public compatibility shim | keep current file, backed by `harness/tools` | Tests and scripts expect this path |
| `tools/run_aether2_g3_official.py` | Official terminal-workflow calibration runner | public compatibility shim | keep current file, backed by `harness/tools` | Imports private Aether-2 helpers today |
| `tools/run_eval_adapter_tool_call_composite_native_smoke.py` | tool-call composite native adapter smoke runner | public compatibility shim | keep current file, backed by `harness/tools` | Eval entrypoint, not core runtime |
| `tools/run_eval_adapter_smoke.py` | tool-call composite-equivalent adapter smoke runner | public compatibility shim | keep current file, backed by `harness/tools` | Eval entrypoint |
| `tools/run_final_harness_eval_suite_baseline.py` | Final-harness baseline evaluator | public compatibility shim | keep current file, backed by `harness/tools` | Long public eval launcher |
| `tools/run_phase_journal.py` | Run-status journaling and classification helpers | move to harness/aether2/monitoring | `harness/aether2/monitoring/run_phase_journal.py` | Generic run accounting, not a CLI-only tool |

### `scripts/*.sh`

| Path | Current role | Recommended classification | Notes |
|---|---|---|---|
| `scripts/build_harnesseng_runtime_bundle.sh` | Runtime bundle packager | public core | Operator-facing packaging script; keep stable |
| `scripts/configure_harnesseng_vm_autoshutdown.sh` | Azure VM auto-shutdown configurator | public core | Ops script; keep as-is |
| `scripts/deallocate_harnesseng_vm.sh` | Azure VM deallocator | public core | Ops script; keep as-is |
| `scripts/deploy_harnesseng_worker_runtime.sh` | Worker deployment and sync orchestration | public core | Ops script; keep as-is |
| `scripts/run_aether2_tournament.sh` | Tournament launcher for Aether-2 task lists | public compatibility shim | Shell wrapper around `tools/run_aether2_g3_official.py` |

### Runner legacy families

| Family | Current role | Recommended classification | Notes |
|---|---|---|---|
| `runner/agent.py`, `runner/model_client.py`, `runner/schemas.py`, `runner/docker_sandbox.py`, `runner/evaluator.py`, `runner/evidence_kernel.py`, `runner/logger.py`, `runner/certified_sandbox.py`, `runner/eval_substrate_*`, `runner/eval_adapter_*`, `runner/final_harness_eval_suite_adapter.py`, `runner/terminal_workflow_paths.py`, `runner/filesystem_agent_context_bench.py`, `runner/tool_call_composite_assets.py`, `runner/azure_openai_env.py`, `runner/kernel_*`, `runner/active_evidence_kernel.py` | Current public core | public core | These are the stable base surfaces the current README already points at |
| `runner/packet04_route_manifest.py`, `runner/eval_runner_router.py`, `runner/eval_batch_runner.py`, `runner/phase65_measurement_contracts.py`, `runner/phase65_measurement_grading.py` | Transitional route/eval bridge layer | public compatibility shim | Still actively imported; should be preserved until callers move |
| `runner/packet03_*`, `runner/packet07_*`, `runner/successor_*`, `runner/phase15_measurement_repair.py` | Historical experiments and replay artifacts | legacy/archive | Preserve for audit/replay only |
| `runner/atomic_eval_diagnostics.py`, `runner/certified_sandbox_backend_probe.py` | Diagnostics/probes | needs decision | Useful but not clearly public-core vs tooling-home yet |

### Tests

| Test family | Current role | Recommended classification | Suggested move target |
|---|---|---|---|
| `tests/test_aether2_*.py` | Aether-2 module/unit coverage | move to tests/harness | `tests/harness/aether2/{runtime,control,verification,env,traces,monitoring}` |
| `tests/test_run_aether2_*.py`, `tests/test_aether2_vm_lifecycle_scripts.py` | CLI / shell wrapper coverage | move to tests/harness | `tests/harness/cli` |
| `tests/test_eval_substrate_*.py`, `tests/test_eval_adapter_*.py`, `tests/test_certified_sandbox_*.py`, `tests/test_final_harness_*.py`, `tests/test_first_eval_core*.py`, `tests/test_phase65_measurement_*.py`, `tests/test_terminal_workflow_failure_probe.py` | Eval substrate, adapters, sandbox, and calibration coverage | move to tests/eval_suite | `tests/eval_suite/...` |
| `tests/test_packet07_*.py`, `tests/test_successor_*.py`, `tests/test_phase65_*.py`, `tests/test_packet_03_*.py`, `tests/test_packet_04_*.py` | Historical campaign coverage | legacy/archive | `tests/eval_suite/legacy` or `tests/archive` |
| `tests/test_active_evidence_kernel.py`, `tests/test_kernel_*.py`, `tests/test_runner.py`, `tests/test_azure_provider_bridge.py`, `tests/test_model_led_substrates.py` | Public core harness/kernel coverage | public core | Keep near current stable runtime packages |

## Recommended Target Tree

```text
harness/
  aether2/
    runtime/
      bridge_harbor.py
      context.py
      executor.py
      jobs.py
      loop.py
      model_client.py
      sessions.py
    control/
      compactor.py
      escalation.py
      loop.py
      prompts.py
    env/
      orientation.py
      grader_isolation.py
    verification/
      verify.py
    traces/
      delta.py
      envelope.py
      mirror.py
      receipts.py
      decision_trace.py
    monitoring/
      cleanup_accounting.py
      metrics.py
      run_phase_journal.py
    tools/
      tools.py
  tools/
    aether2_genericity_check.py
    aether2_targeted_board.py
    aether2_fake_progress_homologs.py
    render_final_harness_scoreboard.py
    run_aether2_g2.py
    run_aether2_g3_official.py
    run_aether2_fake_progress_runner.py
    run_eval_adapter_smoke.py
    run_eval_adapter_tool_call_composite_native_smoke.py
    run_final_harness_eval_suite_baseline.py
```

## Migration Risks

1. `tools/run_aether2_g2.py` and `tools/run_aether2_g3_official.py` import private helpers from `runner.aether2.bridge_harbor`. Moving that module without a shim will break both CLIs immediately.
2. `tests/test_run_aether2_tournament.py` explicitly checks that the launcher imports `runner.aether2.bridge_harbor`, so the shell wrapper and the test need a coordinated update.
3. The Aether-2 unit tests import nearly every submodule directly. A hard move to `harness/aether2/*` will require either per-module alias shims or a package-level import bridge.
4. `runner/README.md` references missing docs files, so documentation may already be out of sync with the actual tree.
5. Several test files import `tools.*` modules that do not exist in this checkout. That is either stale test debt or a separate generated-tooling layer; either way, it is a migration blocker if left unresolved.

## Import / Test Update Notes

- Keep `runner/aether2/__init__.py` as the stable public import surface during migration.
- Preserve module-level aliases for `runner.aether2.bridge_harbor`, `runner.aether2.loop`, `runner.aether2.model_client`, `runner.aether2.verify`, `runner.aether2.delta`, `runner.aether2.envelope`, `runner.aether2.orientation`, `runner.aether2.receipts`, `runner.aether2.sessions`, `runner.aether2.jobs`, `runner.aether2.metrics`, `runner.aether2.cleanup_accounting`, and `runner.aether2.tools`.
- Move the corresponding `tests/test_aether2_*.py` files with the code, not after the code, so that the new tree is verified at the same granularity.
- Keep shell-facing entrypoints stable until their callers are updated; the top-level `tools/*.py` names are part of the current public API.
- Update `pyproject.toml` when the move happens: the current file has only bare dependencies and pytest config, so there is no package discovery or console-script declaration to absorb the new tree automatically.

## Stale / Legacy / Noisy

- `runner/packet07_*` and `runner/successor_*` are historical replay/experiment material and should be treated as archive-only.
- `runner/phase15_measurement_repair.py` is transitional legacy.
- `tools/run_aether2_fake_progress_runner.py` is a deliberate reserved placeholder, not a real runner.
- The missing `tools.*` modules referenced by tests are noisy and should be either restored, aliased, or deleted from the test surface.
- `runner/README.md` is partially stale because it points at absent docs.

## Open Questions

1. Should the public namespace become `harness/` immediately, or should we keep `runner.aether2` and `tools.*` as long-lived compatibility shims?
2. Should `aether2_grader_isolation.py` live with env contracts or with eval tooling?
3. Do we want `run_phase_journal.py` to become monitoring infrastructure under `harness/aether2/monitoring`, or stay as a shared tool helper?
4. Are the missing `tools.*` imports intentional generated artifacts, or should they be restored as first-class checked-in modules?
5. Should `runner/packet04_route_manifest.py` and the `phase65_measurement_*` pair remain public compatibility shims, or be folded into a dedicated eval-suite package before the next split?
