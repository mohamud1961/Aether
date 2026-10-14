# jobctl

Helpers for running local command-line jobs in the background.

`JobRunner.start(name, argv)` launches a job. `join(job)` returns its result. `cancel(job)`
sends SIGTERM to the job's pid. `join()` returns whichever job finished next, and
`deliveries` is a set of finished job names.

This README is from the first draft. The behaviour the team agreed on is in
`docs/runner_contract.md`.
