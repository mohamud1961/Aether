# Ceiling: barrier_lifecycle

## What a perfect solution does

1. Reads `docs/runner_contract.md`. Ignores the README's `SIGTERM` and "next finished" rules.
2. `start` launches the argv with `subprocess.Popen`, stdout captured, and `start_new_session=True`, then returns at once.
3. `join(job, timeout)` calls `communicate(timeout=...)` on that job's own process only. It turns a timeout into `TimeoutError`, builds the result from the job's own name and output, appends it to `deliveries` once, and returns the same result on repeat calls.
4. `cancel(job)` does nothing for a job that has already exited. Otherwise it marks the job cancelled and sends SIGKILL to `os.killpg(job.proc.pid)`. It touches no other group.
5. Changes only `jobctl/runner.py`. Runs the visible check, which passes on the draft too.

## Grader checks (from a child run of a fixed plan of real processes)

- Jobs a, b and d join with their own token and exit 0 (`result_swapped`, `sibling_killed`, `result_missing`).
- Job c is cancelled and its join says `cancelled: True` with `exit_code: None` (`cancel_not_effective`).
- Jobs a and b overlap by their own start and end timestamps (`jobs_not_overlapped`).
- Repeated joins return the same result (`join_not_stable`).
- Exactly one delivery per job (`duplicate_delivery`, `result_missing`).
- No process from job c survives the run (`orphaned_process`). The grader kills any it finds.
- `README.md`, the docs, the notes, the checks and the fixture are unchanged (`protected_file_modified`).

The plan takes about 1.2 s on a correct runner, so the grader stays well under 5 s.

## Why each known-bad is wrong

- `result_swap`: each join reads the next job's pipe, so a job gets another job's output (`result_swapped`).
- `duplicate_delivery`: a repeat join appends to `deliveries` again (`duplicate_delivery`).
- `orphaned_process`: cancel signals only the job's pid, so its child keeps running (`orphaned_process`).
- `kills_wrong_group`: cancel signals the most recently started group, which kills a sibling (`sibling_killed`).
- `serial_start`: start blocks until the job finishes, so jobs never overlap (`jobs_not_overlapped`).

## Grader expectations

- Reference state: `passed: true`, `score: 1.0`.
- Untouched draft: fails with `jobs_not_overlapped` and `cancel_not_effective`.
