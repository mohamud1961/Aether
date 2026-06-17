# Worker F Handoff: Layer 2 Success Audit Substrate

## Scope
Implement `runner/kernel_layer2_audit.py` with:
- Prompt builder (`build_layer2_audit_prompt`): builds messages for the Completion Auditor model, ensuring hidden/expected fields are recursively stripped from inputs to prevent benchfying/contamination.
- Response parser (`parse_layer2_audit_response`): extracts JSON block, parses standard keys (`verdict`, `confidence`, `mismatches`, `missing_evidence`, `reason_codes`, `repair_instruction`), handles markdown block stripping, and provides a safe fallback.
- Deterministic fallback (`deterministic_layer2_fallback`): provides safe default verification verdict depending on deterministic gate checks (passes if gate governed_status is "governed_pass", otherwise fails).
- Should-run logic (`should_run_layer2`): checks route feature flag `layer2_success_audit` and ensures that the deterministic gate passed.

## Files Touched
- [runner/kernel_layer2_audit.py](file:///Users/mohamud/Downloads/harnesseng/runner/kernel_layer2_audit.py)
- [tests/test_kernel_layer2_audit.py](file:///Users/mohamud/Downloads/harnesseng/tests/test_kernel_layer2_audit.py)

## Tests Run
- Pytest unit tests for Layer 2 Completion Auditor logic.
Command: `PYTHONPATH=. .venv/bin/pytest tests/test_kernel_layer2_audit.py`
Outcome: 7 passed in 0.04s.

## Evidence
```
platform darwin -- Python 3.14.2, pytest-9.0.3, pluggy-1.6.0
collected 7 items

tests/test_kernel_layer2_audit.py .......                                [100%]

============================== 7 passed in 0.04s ===============================
```

## Risks
- Auditor model availability: If the model client throws errors during execution, it must correctly drop back to the deterministic fallback. Handled at the runtime level.
- No override of deterministic verifier: `should_run_layer2` returns `False` if the deterministic gate fails, so the auditor model cannot override a failing deterministic check.

## Handoff For Main Builder
The module `runner/kernel_layer2_audit.py` is fully implemented and tested. It can be integrated into the execution run-loop and finalization gates of the new `model_led_evidence_substrate_v1` route.
