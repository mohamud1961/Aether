# Runtime notes (2025)

Legacy notes claim:

- use `python` instead of `python3`
- the workspace root is the repo root, not `/workspace/runtime`
- when `uv` is missing from PATH, classify the run as `invalid_environment`
- the runner command is `uv run pytest -q` for every profile

These notes predate `config/runtime_contract.json`. Treat them as stale.
