# Local proxy accounting repair

Status: **implemented and locally tested; not deployed and not a qualified
all-in spending cap**. Source: `tools/luna_proxy/proxy.py` on the isolated
state branch. The provider and network in the tests are synthetic localhost
servers; no VM, model, Azure endpoint or credential is used.

## Reproduced and repaired

- The previous proxy booked a stream containing the rate-limit phrase as zero
  even when the phrase was model output, or output preceded an error.
  Detection now requires a structured error event and no output events.
- A no-usage stream or direct HTTP error retains its reservation and remains
  inexact. A structured rate-limit event is telemetry, not proof of the bill.
- An exception before the upstream response formerly left the rate-limit flag
  uninitialized and stranded its in-memory reservation. The flag is now
  initialized before the attempt, the reservation is booked, and a row is
  emitted.
- Usage must contain nonnegative input, cached-input and output counts with
  cached ≤ input. Partial usage no longer becomes an exact zero-output bill.
  Fully reported reasoning tokens are recorded but not added to output twice.
- Invalid or negative `max_output_tokens` values are rejected before
  upstream, and unrounded accounting amounts are persisted. When observed
  usage exceeds its reservation, new requests stop; the recorded violation
  remains latched after a clean restart.

The real proxy was run against the local fake provider: 15 integration cases
pass, including known-bad streams, a setup error, partial usage, invalid token
limits and restart after an observed reservation violation. The six original
bug controls all failed before this repair.

## Remaining hard-cap blockers

The input reserve still uses an estimated characters-to-tokens ratio and can
be too low. The violation latch acts only *after* an under-reserved call has
occurred. In-flight reservations are held in process memory and are not
crash-durable; concurrent provider calls, missing usage, pound/dollar
conversion, prior spend and VM charges have not been qualified end to end.
The proxy still has an adjustable local cap. Consequently neither this patch
nor a green synthetic test proves that the user's £5 all-in limit will be
enforced. No paid study should use it as that guarantee without a separately
qualified admission/accounting mechanism.

## RAW_LEDGER_UPDATE

`status=partial`; `scope=local proxy no-usage/error and accounting repair`;
`tests=15 synthetic localhost integration cases passed`;
`provider_calls=0`; `vm_calls=0`; `deployed=no`;
`hard_cap=not_qualified`; `next=independent review and durable,
conservatively bounded admission qualification before any paid run`.
