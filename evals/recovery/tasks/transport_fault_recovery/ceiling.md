# Ceiling: transport_fault_recovery

## What a perfect solution does

1. Reads `docs/transport_contract.md` and ignores the stale v1 rules in `README.md` and `notes/`.
2. Classifies each reply from the status and the body. A 429 is `rate_limited` and is retried for any method. A 2xx body that is a complete JSON object with `value` is `ok`. A 2xx body that is cut off is `truncated`, even when a value-like fragment is in it. A `ConnectionDropped` is `dropped`. Any other status is `fatal`.
3. Retries `rate_limited` for any method. Retries `dropped` and `truncated` only for GET, PUT and DELETE. Never retries `fatal`. Stops at 4 attempts per operation.
4. Records one attempt entry for every transport call, with the label that describes what the transport actually did.
5. Returns `results` for the ops that ended `ok`, and `failed` for every other op, each listed once.
6. Changes only `wirekit/batch.py`. Runs the visible check and sees `passed`, which proves only the shape.

## Grader checks (end state, from an isolated child run)

- The candidate's `results` and `failed` match the scripted outcomes (`result_value_mismatch`, `failed_list_mismatch`).
- The served attempts for each op are exactly the scripted prefix the policy should consume. Stopping early is `premature_stop`. Retrying a fatal is `fatal_retried`. Retrying a non-idempotent op after a dropped or truncated reply is `unsafe_retry`. Going past the budget is `retry_budget_exceeded`. Any other extra call is `unexpected_retry`.
- The candidate's attempt log matches the served outcomes per op. A missing record is `attempt_record_missing`, an extra one is `phantom_attempt_record`, a wrong label is `attempt_label_mismatch`, and a malformed record is `attempt_record_invalid`.
- The candidate must not crash (`candidate_crashed`) or return the wrong shape (`candidate_shape_invalid`).
- `wirekit/errors.py`, the docs, the notes, the README and the checks are unchanged (`protected_file_modified`).

## Why each known-bad is wrong

- `retry_fatal`: a fatal reply is retried, so the next call is served as ok. `fatal_retried`.
- `post_retry_unsafe`: a dropped POST is retried, which could apply the write twice. `unsafe_retry`.
- `trust_partial_body`: a cut-off body yields a value from a fragment. `result_value_mismatch`, and the log labels it as ok.
- `omit_rate_limit_records`: the retries happen, but the log is short. `attempt_record_missing`.
- `mislabel_drop_as_rate_limit`: the retry decision is right, but the log says the wrong thing. `attempt_label_mismatch`.
- `patch_treated_idempotent`: follows the stale README, so a dropped PATCH is retried. `unsafe_retry`.
- `gives_up_on_rate_limit`: a 429 ends the op at once, as the v1 notes say. `premature_stop`.

## Grader expectations

- Reference state: `passed: true`, `score: 1.0`.
- Untouched workspace: fails, with `attempt_record_missing`, `premature_stop` and `unsafe_retry` among the reasons.
