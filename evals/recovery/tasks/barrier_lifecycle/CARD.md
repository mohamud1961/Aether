# Task card: barrier_lifecycle

Admission: **debug**. The grader starts the candidate runner in a child interpreter, and that runner launches real local processes. Use it only with the reference and control runners, not with model agents.

Ported from the archived M2 barrier-lifecycle diagnostic (`evals/m2_barrier_lifecycle_v1`). That pack ran fixed JSON plans against a scripted driver and proved only the fixture. This task asks for the runner itself, graded by its end behaviour: overlap, association, delivery and process-group scope.

## Design

- The contract is in `docs/runner_contract.md`. The README is a stale distractor that suggests SIGTERM and "next finished" joins.
- The draft runs jobs serially and passes the visible check, which proves only that the API exists.
- Real subprocesses, short by design: about 1.2 s for a correct runner.
- The grader inspects the process table after the child exits. It kills any leftover process it finds, so a failing run leaves nothing behind.

## Controls

- Known-bad: 5 scripts (`known_bad/`), each a single-rule mutation of the reference.
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Reason coverage

| Reason | Controls |
|---|---|
| result_swapped | known_bad result_swap |
| duplicate_delivery | known_bad duplicate_delivery |
| orphaned_process | known_bad orphaned_process; careless skip_check |
| sibling_killed | known_bad kills_wrong_group |
| jobs_not_overlapped | known_bad serial_start; careless do_nothing, wrong_target |
| cancel_not_effective | careless fake_it, half_done |
