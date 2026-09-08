# Runtime surface

This document describes the **current production code surface**, not historical Aether architectures.

The canonical public entrypoints are:

```text
aether
aether.launch
aether.harbor_agent
```

From there, the current execution path is broadly:

```text
aether.launch
  ↓
Harbor lifecycle / isolated task environment
  ↓
aether.harbor_agent:AetherHarborAgent
  ↓
aether.harbor_runtime
  ↓
aether.run_adapter
  ↓
aether.kernel + turn modules
  ↓
execution / context / receipts / verifier / evidence
  ↓
Harbor official evaluation
```

## Machine-measured current graph

Aether's public qualification now parses every tracked `aether/**/*.py` file with Python's AST and computes static intra-package reachability from the canonical roots above.

On commit `5d38a6b019192f78d272575095a2a91c81c3c6bb`, the clean GitHub runner measured:

```text
production Python modules: 100
production Python source: 1,825,131 bytes
statically reachable modules: 97
static unreached modules: 3
```

The full graph is preserved in every qualification artifact as `runtime-surface.json`.

Generate it locally with:

```bash
python tools/runtime_surface_report.py \
  --json runtime-surface.json \
  --text runtime-surface.txt
```

## Why the three static exceptions are expected

The static exceptions on that checkpoint are:

```text
aether.mcp_environment_client
aether.rfb_computer_client
aether.providers
```

They are not three unexplained dormant runtimes.

### `aether.mcp_environment_client`

This is a small standard-library MCP bridge that is **uploaded into the Harbor task environment** by `HarborEnvironmentExecutor`. It runs from the task world so Compose/network names resolve from the task environment rather than from the Aether host.

The executor places the bridge under `/tmp`, not in the grader-visible workspace, and removes it deterministically when the executor closes. It is execution transport infrastructure, so it is intentionally not imported into the host runtime graph.

### `aether.rfb_computer_client`

This is the equivalent task-environment bridge for native RFB/VNC computer control. It contains protocol/action transport rather than task or UI strategy.

`HarborEnvironmentExecutor` uploads it under `/tmp` when that backend is needed and removes it on close. Again, absence from the host static import graph is an architectural boundary, not evidence of an alternate agent.

### `aether.providers`

`aether/providers/__init__.py` is only the package namespace marker/docstring. Provider implementations beneath it are reached directly/lazily from the production model boundary; the namespace module itself has no behavioural role.

## What the graph does and does not prove

The report is useful because it turns production-surface drift into inspectable evidence. It can show that a new Python module appeared, that a module disconnected from canonical roots, or that a previously separate surface became imported.

It does **not** prove that every reached module executes on every task, nor that every unreached module is dead. Static analysis cannot fully see runtime registries, uploaded helper programs, string-selected components, or other dynamic loading.

That is why Aether reports the exceptions rather than deleting or relabelling them automatically.

## Historical implementation names inside current code

Some current source identifiers preserve development-lineage names such as `AetherNextKernel`, `PCR`, `postmerge_*`, and adapter version strings such as `s3-harbor-v1`.

Those names are **implementation lineage identifiers inside the one current Aether runtime**. They do not denote parallel production agents, an active Aether-2 runtime, a production Architect, or a second benchmark runner.

Renaming qualified runtime symbols purely for presentation would create unnecessary pre-funding regression risk. Current authority is therefore determined by the entrypoints, package graph and qualification checks—not by whether every internal symbol has been cosmetically renamed.

## Authority order

For questions about what is currently production:

1. `aether = aether.launch:main` — installed console boundary;
2. `aether.harbor_agent:AetherHarborAgent` — Harbor adapter;
3. `aether/` — production implementation;
4. `tools/check_production_surface.py` — fail-closed production identity/neutrality guard;
5. `tools/runtime_surface_report.py` — static graph receipt;
6. `tests/` — deterministic qualification;
7. `evidence/` — empirical run evidence;
8. `research/` and frozen `tracking/` material — historical context/provenance only.

See [`ARCHITECTURE.md`](ARCHITECTURE.md), [`QUALIFICATION.md`](QUALIFICATION.md), and [`EVIDENCE_PIPELINE.md`](EVIDENCE_PIPELINE.md) for the complementary architecture, reproducibility and run-evidence views.
