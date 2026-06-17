# Aether-2

Canonical public package boundary for the Aether-2 harness line.

## Implemented Code

- `runtime/`: workspace execution, sessions, jobs, model client, orientation,
  prompts, and verification support.
- `control/`: loop and orchestration boundary.
- `tools/`: canonical tool schema and dispatch surface.
- `traces/`: evidence, delta, envelope, mirror, and receipt primitives.

## Navigation-Only Subpackages

- `agents/`
- `cli/`
- `env/`
- `hooks/`
- `monitoring/`
- `skills/`
- `verification/`

## Compatibility

`runner.aether2` remains available as a legacy import path, but new code should
prefer `harness.aether2`.
