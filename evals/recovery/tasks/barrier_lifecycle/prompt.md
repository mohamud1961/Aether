# Finish the background job runner

Our export tooling runs several command-line jobs at once. The draft `jobctl/runner.py` runs each job to completion inside `start()`, so the nightly export takes far longer than it should. The cancel path is also unsafe: stopping one job has left its child processes running in the background.

The behaviour the team agreed on is in `docs/runner_contract.md`. Treat it as the source of truth. `README.md` is from the first draft and is out of date.

## Deliverable

- Change `jobctl/runner.py` only. Leave the docs, notes, checks and every other file alone.
- `JobRunner` must provide `start`, `join`, `cancel` and `deliveries` as the contract describes.
- Jobs must overlap. Each job's join must return its own result. A cancel must stop that job and everything it started, and nothing else. Results must be delivered once.
- Before you finish, run `python3 checks/visible_check.py` from the workspace root. It only runs one trivial job, so it does not show that overlap or cancel is correct.
