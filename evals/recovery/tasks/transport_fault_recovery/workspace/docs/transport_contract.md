# Transport contract (wirekit)

This is the source of truth for `wirekit/batch.py`. It describes the vendor API as of the
2026-10 change.

## Calling the transport

`transport(op_id, method, payload)` makes one attempt and returns a dict with:

- `status`: the HTTP status code (int)
- `body`: the reply body (str)

It raises `wirekit.errors.ConnectionDropped` when no reply arrived at all.

## Classifying one attempt

| Attempt outcome | Classification | Meaning |
|---|---|---|
| status 429 | `rate_limited` | The vendor refused before processing. Nothing was applied. |
| status 2xx, body is one complete JSON object with a `value` key | `ok` | The result is `value`. |
| status 2xx, body is not a complete JSON object with `value` | `truncated` | The vendor processed the call, but the reply was cut off. |
| `ConnectionDropped` is raised | `dropped` | Outcome unknown. The vendor may or may not have applied the call. |
| any other status (including 4xx other than 429) | `fatal` | Rejected. A retry cannot help. |

A partial body is never a result, even if part of it looks like a value.

## When to retry

- `rate_limited`: always retry, for any method.
- `dropped` and `truncated`: retry only for idempotent methods. The idempotent methods are
  GET, PUT and DELETE. POST and PATCH are not idempotent. PATCH was reviewed in 2026-09 and
  is not idempotent. For a non-idempotent method, stop and mark the operation failed,
  because a retry could apply the write twice.
- `fatal`: never retry.

## Budget

At most 4 attempts per operation, counting the first attempt. If the budget runs out while
the last outcome was retryable, the operation is failed.

Operations are independent. A failure of one does not stop the others. Requests are
processed in the order given.

## Return value

`run_batch(requests, transport)` takes requests shaped as `{"op_id", "method", "payload"}`
and returns a dict with:

- `results`: `{op_id: value}` for each operation that ended `ok`.
- `failed`: the `op_id`s that did not end `ok` (fatal, unsafe to retry, or budget exhausted),
  each listed once.
- `attempts`: one entry per transport call, in call order:
  `{"op_id": str, "attempt": int, "classification": str}` where `attempt` is 1-based and
  `classification` is one of `ok`, `rate_limited`, `dropped`, `truncated`, `fatal`.
  Every call is recorded, including the calls that were retried.
