# Accepted Findings Resolution: Model-Led Evidence Substrate v1

This document records the resolution of the findings raised in the adversarial architecture review (`adversarial_review_01.md`).

---

## 1. Resolution of Findings

### Finding 1: Layer 2 Completion Audit Call is Dead Code
- **Status:** Resolved.
- **Action taken:**
  Integrated the Layer 2 model-led completion check inside the `run_loop` of `runner/active_evidence_kernel.py`. When the solver returns a decision to finalize:
  1. We execute the deterministic finalization check first. If it fails, we record the failure, set the recovery card, and continue the loop to let the solver repair (without calling the Layer 2 model).
  2. If the deterministic check passes, we check `should_run_layer2`. If enabled, we call `build_layer2_audit_prompt` and execute the model audit.
  3. If Layer 2 returns `PASS`, the run completes and breaks the loop.
  4. If Layer 2 returns `FAIL` or `UNCLEAR`, we feed the repair instructions and mismatches back to the solver, record the failure, increment the verification cycle counter, and continue.
  5. If the verification fails 3 times, we close the run with the final Layer 2 diagnosis.
  6. Added a feature flag check so legacy routes bypass this check and break immediately.

### Finding 2: Missing Success Contract Prompt Instruction
- **Status:** Resolved.
- **Action taken:**
  Added check inside `run_loop` before `model.complete`. If `model_led_success_contract` is active and the success contract status is `"not_declared"`, we dynamically append a system instruction to history prompting the solver to declare a contract, and register `success_contract_missing` in open obligations.

### Finding 3: Success Contract Obligation Finalization Blocking
- **Status:** Resolved.
- **Action taken:**
  Updated `_evaluate_finalization_gate` in `runner/kernel_gates.py` to check for `success_contract_missing` in `open_obligations`. If present, it blocks `governed_pass` by setting `governed_status = "ungoverned_model_claim"` and adding reason code `"success_contract_missing"`.
  Also updated `KernelState` in `runner/kernel_state.py` to dynamically include `success_contract_missing` in its open obligations list when `model_led_success_contract_active` is enabled and contract status is `"not_declared"`.

### Finding 4: Context Pack Compaction uses Hard Truncation
- **Status:** Resolved.
- **Action taken:**
  Updated `build_context_pack` to inject `model_led_active` into the pack.
  Updated `render_context_pack` to completely skip hard slicing/truncation of the JSON string if `model_led_active` is True. Legacy routes continue to use the legacy slicing behavior to preserve compatibility.

---

## 2. Verification Evidence

All 21 unit tests (including newly added coverage for the slicing skip, success contract obligations, and gate blocking logic) pass cleanly:

```text
tests/test_model_led_substrates.py ..............                        [ 66%]
tests/test_kernel_layer2_audit.py .......                                [100%]
============================== 21 passed in 0.13s ==============================
```

Legacy route regression check also passes cleanly:
```text
tests/test_active_evidence_kernel.py ..................................  [100%]
============================== 34 passed in 1.06s ==============================
```
