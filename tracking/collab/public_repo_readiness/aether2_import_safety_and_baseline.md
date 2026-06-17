# Aether-2 Import Safety & Test Baseline (Phase-B contract)

Status: `AUTHORITATIVE_SAFETY_CONTRACT` — Date: 2026-06-16

Purpose: guarantee the live runtime (`harness/aether2/`, imported via `runner.aether2.*`
shims) keeps importing and testing through the public restructure. Nothing here is
"new code" — it is the move/relocation contract for the existing runtime.

## 1. Aether-2's complete `runner/` dependency closure

The live harness imports from `runner/` in exactly these places:

| Importer (live harness) | Imports | From |
|---|---|---|
| `harness/aether2/control/loop.py` | `_clean_hidden_refs` | `runner.kernel_layer2_audit` |
| `harness/aether2/runtime/verify.py` | `_clean_hidden_refs` | `runner.kernel_layer2_audit` |
| `harness/aether2/traces/delta.py` | `_sha256_file`, `build_artifact_record` | `runner.kernel_artifacts` |
| `harness/aether2/runtime/metrics.py` | `extract_command`, `infer_action_type` | `runner.action_bus` |
| `harness/aether2/runtime/model_client.py` | `ModelClientError`, `TRANSIENT_STATUS_CODES`, `make_model_client_from_route` | `runner.model_client` |
| `harness/aether2/runtime/bridge_harbor.py` | `make_azure_gpt53_codex_route_from_env`, `make_azure_gpt54_mini_route_from_env` | `runner.model_client` |

Transitive closure (all stdlib-only beyond this chain — no third-party surprises):

```
model_client.py (1551)  -> schemas.py (508)  [validate_model_route]
                        -> kernel_tpm_pacer.py (413, lazy import)
action_bus.py (134)          [stdlib only]
kernel_layer2_audit.py (267) [stdlib only]
kernel_artifacts.py (782)    [stdlib only]
```

Total closure = **6 modules**. No other `runner/*` module is reachable from the live runtime.
=> The other ~100 `runner/` files (packets, successors, phase65, eval_batch_runner, old
agent.py, etc.) are NOT load-bearing for aether2 and can be excluded/quarantined freely.

## 2. Self-containment relocation plan (move-only + 3 tiny helper extractions)

Goal: `harness/` depends on nothing under `runner/`. Then `runner/` leaves the public tree
entirely, and the kernel files become whole-harness variants under `variants/harness/`.

| Module | Action | New home | Importers to update |
|---|---|---|---|
| `runner/model_client.py` | move (runtime model backend) | `harness/aether2/runtime/model_routes.py` | model_client.py, bridge_harbor.py, tools/run_final_harness_eval_suite_baseline.py |
| `runner/schemas.py` | move route-validation (or whole) | `harness/aether2/runtime/` | model_routes |
| `runner/kernel_tpm_pacer.py` | move | `harness/aether2/runtime/` | model_routes |
| `runner/action_bus.py` | move | `harness/aether2/runtime/action_bus.py` | metrics.py |
| `runner/kernel_layer2_audit.py` `_clean_hidden_refs` | **extract helper** | `harness/aether2/traces/` (redaction util) | loop.py, verify.py |
| `runner/kernel_artifacts.py` `_sha256_file`,`build_artifact_record` | **extract helpers** | `harness/aether2/traces/artifacts.py` | delta.py |

After extraction, the *full* `kernel_layer2_audit.py` and `kernel_artifacts.py` files move to
`variants/harness/` as historical whole-harness variant evidence — `harness/` no longer
imports them, so no layering violation (runtime must not depend on experiments).

Keep `runner.aether2.*` shims pointing at `harness.aether2.*` (already in place) for back-compat
during migration; they can be retired in a later commit.

## 3. Green test baseline (must be preserved)

Command:
```
.venv/bin/python -m pytest tests/test_aether2_*.py \
  tests/test_kernel_layer2_audit.py tests/test_kernel_artifacts.py tests/test_action_bus.py \
  tests/test_kernel_tpm_pacer.py tests/test_azure_openai_model_client.py -q
```
Result on 2026-06-16 **before** any restructure: **302 passed, 1 failed (80s)**.

Known PRE-EXISTING failure (not introduced by restructure):
- `tests/test_action_bus.py::test_infer_action_type_maps_native_and_service_probe_cases`
  expects `infer_action_type(tool_name="raw_bash", command="python3 launch_service.py --port 8080")`
  == `"start_service"`, but it returns `"command"`. Candidate small quality fix when
  `action_bus` is relocated (detect service-launch scripts / `--port`).

Phase-B gate after every slice: **302 passing, zero new failures.** Re-run the command above.

## 4. Broken-collection tests (28) — all in the excluded surface

The 28 collection errors in the full suite are entirely legacy/eval-adapter:
`packet07_* (7)`, `run_* (7)`, `eval_adapter_{tool_call_atom,retrieval_context,filesystem_agent,terminal_workflow,native_attempt_wrappers} (5)`,
`tool_call_composite_native_certified_attempt`, `first_eval_core{,_certified}`, `eval_substrate_smoke`,
`eval_suite_orchestrator`, `overnight_control_plane`, `ingest_final_harness_recipe_candidates`,
`goal1b_tooling_family_sprint`, `clean_tool_contract_diagnostic_family`.
These travel with their excluded/quarantined source modules and must NOT pollute the public
`tests/` tree.
