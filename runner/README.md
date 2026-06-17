# Runner Package Orientation

`runner/` is the compatibility and historical surface. New public code should
prefer `harness/` and, for the Aether-2 line, `harness.aether2`.

## Compatibility Surface

- `runner/aether2/`: legacy namespace retained for import compatibility.
- `runner/agent.py`: current runner entrypoint surface.
- `runner/kernel_*.py`: runner-side infrastructure modules.
- `runner/benchmark_adapter_*.py`: benchmark adapter entrypoints.
- `runner/phase65_measurement_contracts.py`
- `runner/phase65_measurement_grading.py`

## Read First

- [Harness architecture map](../docs/architecture/public-architecture.md)
- [Aether namespace compatibility map](../tracking/collab/public_repo_readiness/aether_namespace_closeout_map.md)

## Status

The public canonical ownership for Aether-2 now lives under `harness/aether2/`.
Use `runner.aether2` only when legacy imports or compatibility tests still need
it.
