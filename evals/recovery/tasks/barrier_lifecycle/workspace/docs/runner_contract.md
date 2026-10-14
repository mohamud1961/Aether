# Job runner contract (jobctl)

`jobctl.runner.JobRunner` runs local command-line jobs in the background so that several of
them can overlap. This is the source of truth for `jobctl/runner.py`.

## start(name, argv) -> Job

- Launches `argv` as a background process and returns at once. It never waits for another job.
- Each job runs in its own session and process group, so the job and every process it starts
  can be signalled together.
- `name` is the label for the job. The job's output is its stdout, captured as text.

## join(job, timeout=None) -> dict

- Waits for that job only and returns its result: `{"name", "exit_code", "output", "cancelled"}`.
  `name` is the job's own label, and `output` is that job's own stdout.
- Joining the same job again returns the same result. A job's result is delivered once.
- If `timeout` (seconds) runs out first, raises `TimeoutError`. The job keeps running.

## cancel(job)

- Kills the job's whole process group: the job and every process it started. Other jobs are
  not touched.
- A cancelled job's join returns `cancelled: True` and `exit_code: None`.
- Cancelling a job that has already exited is a no-op. Its join reports the real exit code and
  `cancelled: False`.

## deliveries

- `runner.deliveries` is a list with exactly one entry per job: the result dict, appended the
  first time that job's result is produced by `join`. Repeat joins add nothing.
