# Aether Namespace Compatibility Map

Date: `2026-06-15`

## Summary

- `runner/aether2/__init__.py` is the package-level compatibility aggregator.
- Every other `runner/aether2/*.py` file is an identity-preserving alias shim.
- No duplicate live implementation remains inside `runner/aether2/`.
- External shared helpers still referenced by canonical code:
  - `runner.model_client`
  - `runner.kernel_layer2_audit`

## Old To Canonical Map

| Legacy module | Classification | Canonical home | Notes |
| --- | --- | --- | --- |
| `runner.aether2.__init__` | package aggregator | `harness.aether2` plus its canonical subpackages | Imports canonical objects directly and preserves the compatibility package surface. |
| `runner.aether2.bridge_harbor` | true alias-only shim | `harness.aether2.runtime.bridge_harbor` | Module identity is shared through `sys.modules`. |
| `runner.aether2.cleanup_accounting` | true alias-only shim | `harness.aether2.runtime.cleanup_accounting` | Module identity is shared through `sys.modules`. |
| `runner.aether2.compactor` | true alias-only shim | `harness.aether2.runtime.compactor` | Module identity is shared through `sys.modules`. |
| `runner.aether2.context` | true alias-only shim | `harness.aether2.runtime.context` | Module identity is shared through `sys.modules`. |
| `runner.aether2.delta` | true alias-only shim | `harness.aether2.traces.delta` | Module identity is shared through `sys.modules`. |
| `runner.aether2.envelope` | true alias-only shim | `harness.aether2.traces.envelope` | Module identity is shared through `sys.modules`. |
| `runner.aether2.escalation` | true alias-only shim | `harness.aether2.runtime.escalation` | Module identity is shared through `sys.modules`. |
| `runner.aether2.executor` | true alias-only shim | `harness.aether2.runtime.executor` | Module identity is shared through `sys.modules`. |
| `runner.aether2.jobs` | true alias-only shim | `harness.aether2.runtime.jobs` | Module identity is shared through `sys.modules`. |
| `runner.aether2.loop` | true alias-only shim | `harness.aether2.control.loop` | Module identity is shared through `sys.modules`. |
| `runner.aether2.metrics` | true alias-only shim | `harness.aether2.runtime.metrics` | Module identity is shared through `sys.modules`. |
| `runner.aether2.mirror` | true alias-only shim | `harness.aether2.traces.mirror` | Module identity is shared through `sys.modules`. |
| `runner.aether2.model_client` | true alias-only shim | `harness.aether2.runtime.model_client` | Canonical implementation still depends on `runner.model_client`, which has no approved public twin yet. |
| `runner.aether2.orientation` | true alias-only shim | `harness.aether2.runtime.orientation` | Module identity is shared through `sys.modules`. |
| `runner.aether2.prompts` | true alias-only shim | `harness.aether2.runtime.prompts` | Module identity is shared through `sys.modules`. |
| `runner.aether2.receipts` | true alias-only shim | `harness.aether2.traces.receipts` | Module identity is shared through `sys.modules`. |
| `runner.aether2.sessions` | true alias-only shim | `harness.aether2.runtime.sessions` | Module identity is shared through `sys.modules`. |
| `runner.aether2.tools` | true alias-only shim | `harness.aether2.tools.native` | Compatibility alias for the canonical tool schema/dispatch module. |
| `runner.aether2.verify` | true alias-only shim | `harness.aether2.runtime.verify` | Module identity is shared through `sys.modules`. |

## Public Export Notes

- Package-level public objects resolve to canonical runtime, control, trace, and tool objects.
- The runner compatibility package no longer imports its own shim modules in the top-level aggregator.
- Legacy paths are retained for backward compatibility only; canonical ownership is now in `harness/aether2/`.
