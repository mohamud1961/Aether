# Aether-2 Slice 4 Bounded Read-Only Verifier

Status: completed

Date: 2026-07-02

## Purpose

Slice 4 makes the verifier a bounded read-only inspector. Aether-2 already had read-only verifier capabilities and bounded verification rounds; this slice closes the missing tool-call budget inside a verifier round and pins the provider transcript invariant.

The verifier may inspect, but it does not solve or mutate. Extra inspection requests are answered with explicit budget-exhausted observations, not silently ignored.

## Adds

- `MAX_VERIFIER_INSPECTION_CALLS = 3`.
- `verify_fresh_context(..., max_inspection_calls=3)`.
- A budget-exhausted tool response for verifier inspection calls beyond the budget.
- An unknown-tool tool response for verifier tool calls that do not map to an available inspection handler.
- Tests proving:
  - only the first three verifier inspection calls execute;
  - every verifier tool call still receives a provider-valid tool response;
  - excess inspection calls are visible as `verification_inspection_budget_exhausted`;
  - unknown verifier tools are visible as `verification_unknown_tool`;
  - mutating verifier commands are rejected and audited by `_ReadOnlyVerificationContext`.

## Changes

- `verify_fresh_context` now answers every verifier tool call in the second verifier message, including unknown and over-budget calls.
- Over-budget inspection calls are not executed.
- Unknown verifier tool calls are not silently dropped.
- Existing read-only verifier context remains the enforcement surface for allowed inspection commands.

## Deletes

- No files were deleted in this slice.
- The silent unmatched-tool-call path for unknown verifier tools was removed.
- The unbounded in-round verifier inspection execution path was removed.

## Deferred

- No expansion of verifier capabilities beyond the existing read-only set.
- No mutation-capable verifier tools.
- No verifier-as-solver behavior.
- No model-backed verifier-loop row was run in this slice.
- Broader completion-authority carve-down remains Slice 5.

## Tests

Passed:

```bash
python3 -m pytest -q tests/test_aether2_verification_feedback.py tests/test_aether2_run_config.py
```

Result: 36 passed in 2.47s

Passed:

```bash
python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng
```

Result: exit 0, no output

Passed:

```bash
python3 -m pytest -q tests/test_aether2_prompts.py tests/test_aether2_run_config.py tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py tests/test_aether2_verification_feedback.py tests/test_compaction_receipt_continuity.py tests/test_aether2_compactor.py tests/test_aether2_transcript_repair.py
```

Result: 70 passed in 3.69s

Passed:

```bash
python3 -m pytest -q tests/test_run_custom_eval_board.py
```

Result: 56 passed in 32.13s

Passed:

```bash
make public-tests
```

Result: 11 passed in 1.04s

## Risk

- A three-call verifier inspection budget may be too small for some complex tasks. It is intentionally conservative and can be revisited with eval evidence.
- Budget-exhausted and unknown-tool responses are model-visible verifier evidence. Downstream logic must treat them as verifier inspection limitations, not task facts.
- The read-only command guard remains best-effort structural enforcement plus audit trail, not a formal shell sandbox proof.

## Rollback

Revert the verifier inspection budget, error tool-message helpers, and tests. That would restore the previous behavior where a verifier could execute all requested inspection calls in a round and unknown tool calls could be silently dropped from the follow-up verifier transcript.
