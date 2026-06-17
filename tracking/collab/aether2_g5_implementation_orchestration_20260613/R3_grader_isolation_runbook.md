# R3 Grader Isolation Runbook

- Helper: `tools/aether2_grader_isolation.py`
- Official-test contract: model the official `/tests` path and the runner-side `/app/tests` path explicitly.
- Hidden-test policy: keep hidden tests out of model-visible context and record the isolation rule instead of exposing content.
- Grader policy: toolchain resolution comes from the grader manifest, not from agent-mutated `PATH` or `PYTHONPATH`.
- Evidence: use the manifest builders and validators in the helper module; do not duplicate hidden-test content in docs or tests.

