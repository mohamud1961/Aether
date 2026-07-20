# Aether-Next Production Path Map

Baseline source: `0cbefbb47fc185baebfca7ceb41101b033554a2b`
Status: integration candidate, NOT READY

## Canonical Docker task path

1. `aether_next/runners/docker_runner.py::run_tbench_task`
   - loads immutable task instruction and task metadata;
   - seeds grader-visible `/app` state;
   - captures initial workspace state;
   - starts the task container;
   - builds and probes EnvMap;
   - constructs model hooks and production kernel;
   - runs kernel;
   - introduces official task/test surfaces only after terminal state;
   - runs official grader;
   - writes result and trace metadata;
   - tears down task resources.

2. `aether_next/run_adapter.py::workbench_architect_for`
   - selects the canonical Workbench Architect path.

3. `aether_next/kernel_config.py::resolve_runtime`
   - obtains Architect config;
   - compiles objective/eval/runtime configuration;
   - returns the production compiled runtime or config blockers.

4. `aether_next/workbench_config.py`
   - parses the model-authored HarnessConfigIR.

5. `aether_next/workbench_compile.py` and `aether_next/compiler.py`
   - mechanically realise config into `CompiledRuntime`;
   - certify proof routes and build config-realisation evidence.

6. `aether_next/kernel.py::AetherNextKernel.run`
   - owns the Solver/Verifier control loop;
   - performs route preflight;
   - compiles per-turn context;
   - obtains and validates Solver turns;
   - dispatches task actions;
   - handles submission and Verifier;
   - performs completion and terminal classification.

7. `aether_next/model_hooks.py` and `aether_next/providers/azure_model.py`
   - own role-specific provider calls, parsing boundary, and provider telemetry.

8. `aether_next/context_compiler.py`
   - produces model-visible dynamic context from ledger state.

9. `aether_next/kernel_dispatch.py`, `aether_next/kernel_turns.py`, and
   `aether_next/runners/docker_exec_executor.py`
   - execute one authorised frontier and record real results/state deltas.

10. `aether_next/ledger.py`
    - append-only runtime evidence, findings, obligations, accounting, and
      queryable result handles.

11. `aether_next/kernel_verifier.py`, `aether_next/verify_completion_protocol.py`,
    `aether_next/verifier_inspector.py`, and `aether_next/verifier_overlay.py`
    - build state-only Verifier packets;
    - execute bounded inspections;
    - parse and route Verifier outcomes.

12. `aether_next/proof_contract.py` and
    `aether_next/verify_completion_gates.py`
    - bridge Verifier evidence into clause proof and enforce structural/evidence
      gates.

13. `aether_next/completion.py::CompletionGate.evaluate`
    - mechanical completion decision.

14. `aether_next/runners/grader_results.py`
    - truthful multi-phase official-grader reconciliation.

## Known duplicate or legacy surfaces

The repository also contains historical/eval/reference paths including:

- `reference_legacy/`;
- replay engines and multiple eval runners;
- older `runtime.py`/bridge surfaces;
- imported V5 tests expecting APIs not exported by the current package;
- task-family capability classification in `task_capability.py`;
- archived boards, snapshots, traces, and run-specific scripts.

These are not automatically production authority. Each must be classified as:

- production retained;
- test/reference only;
- migration source;
- remove/quarantine.

## One-path target

Certification requires exactly one authoritative implementation for:

- provider extraction;
- Solver turn parsing;
- observation boundary;
- action dispatch;
- state generation;
- proof registration;
- finding lifecycle;
- Verifier inspection;
- completion;
- evidence finalisation.

Any alternate path capable of executing production task state or declaring
completion blocks scorecard item A2.
