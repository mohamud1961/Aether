# Task card: transport_fault_recovery

Admission: **debug**. The grader imports and executes the candidate `wirekit/batch.py` in a child interpreter. Use it only with the reference and control runners, not with model agents.

Ported from the archived F10 transport candidates (`candidates/transport`). The reference client and the alternate client both use a per-call simulator; this task replaces that with an in-process scripted transport and adds three v2 traps: a stale README retry policy, a PATCH idempotency rule that the stale README gets wrong, and a truncated body that contains a value-like fragment.

## Design

- The contract is in `docs/transport_contract.md`. The README and `notes/` are stale distractors.
- The grader drives `run_batch` through a scripted transport and compares three things: the candidate's results and failed list, the served outcomes per op, and the candidate's attempt log.
- The visible check tests only the function shape.

## Controls

- Known-bad: 7 scripts (`known_bad/`), each a single-rule mutation of the reference.
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Reason coverage

| Reason | Controls |
|---|---|
| fatal_retried | known_bad retry_fatal |
| unsafe_retry | known_bad post_retry_unsafe, patch_treated_idempotent; careless half_done |
| result_value_mismatch | known_bad trust_partial_body |
| attempt_record_missing | known_bad omit_rate_limit_records; careless do_nothing, fake_it, wrong_target |
| attempt_label_mismatch | known_bad mislabel_drop_as_rate_limit |
| premature_stop | known_bad gives_up_on_rate_limit; careless skip_check |

The grader's reason codes for crashes, shape, extra calls and budget overrun are guards without a dedicated control.
