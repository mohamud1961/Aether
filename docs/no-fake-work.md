# No Fake Work

A change is done only when it does real work, proven by evidence independent of the author's
own claims. Making a check turn green is not the goal; making the underlying thing true is.

## Never acceptable

- A file, asset or shim that exists only to satisfy an existence or import check. If a report
  says `X_present: true`, `X` must be real and functional.
- No-op swallow-all shims, stub functions returning canned values, or synthetic placeholder
  data presented as real.
- Passing a test or preflight by weakening it, mocking past it, or feeding it synthetic data
  that masquerades as real.
- Claiming fixed, ready or green when the green comes from mocks, stubs, shims or
  import success rather than real execution.

## Required

- Distinguish "imports succeed" from "really works", and report which.
- When real assets or dependencies are missing, report **blocked**, with the exact missing piece.
  An honest blocked beats a fake green.
- Make every check falsifiable: a known-bad input must fail it.
- Review audits faithfulness: open the files behind any green and confirm real code and data
  before accepting a "done" claim.
