# `harness.aether2`

This directory anchors the public `harness.aether2` import namespace.

The current implementation lives under the repo-local `aether/` tree and is
re-exported here through `__init__.py`.

Why this exists:

- `harness.aether2` is the canonical public import path.
- `runner.aether2` remains a compatibility shim for older imports.
- The implementation tree is still organized under `aether/` while the public
  namespace migration is stabilized.

Reviewer note:

- import `harness.aether2.*` when checking public package behavior;
- browse `aether/` when you want the current source files.
