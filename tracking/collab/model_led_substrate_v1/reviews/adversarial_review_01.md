# Adversarial Architecture Review: Model-Led Evidence Substrate v1

This document provides a critical assessment of the actual implementation of `model_led_evidence_substrate_v1` against the specifications outlined in `model_led_variant_synthesis.md` and `model_led_substrate_implementation_plan.md`.

---

## 1. Executive Summary of Implementation Discrepancies

While the core modules (`kernel_success_contract.py`, `kernel_artifacts.py`, `kernel_layer2_audit.py`, `kernel_native_tools.py`) are implemented, passing their isolated unit tests, their **integration into the execution pipeline is incomplete**. Specifically:
1. The **Layer 2 model-led completion audit is completely dead code** during solver execution. It is never invoked or run inside the main loop, violating the verify-repair loop requirements.
2. The **Success Contract prompt instruction is missing**, meaning the solver is never prompted to declare a success contract.
3. The **Success Contract finalization blocks are missing**, allowing finalization to pass even when a success contract is absent.
4. **Context pack rendering uses hard truncation** (`compact[:6000]`), violating the constitutional rule against character slicing of JSON.

---

## 2. Detailed Gap Analysis

### Gap 1 (Critical): Layer 2 Completion Audit Call is Dead Code
- **Design Spec:**
  Under *Completion Flow* in `model_led_variant_synthesis.md` and *Phase 4: Layer 2 Success Audit* in the implementation plan, the harness must execute the model-backed Layer 2 completion audit when the solver claims done. If it returns `FAIL` or `UNCLEAR`, the harness must inject the `repair_instruction` and allow the solver to continue, for up to 3 repair cycles.
- **Actual Code:**
  In `runner/active_evidence_kernel.py` (`run_loop`), when the solver claims done, the loop immediately terminates:
  ```python
  if decision.get("action") == "finalize":
      status = "completed"
      break
  ```
  The execution never invokes `build_layer2_audit_prompt` or `parse_layer2_audit_response` to run a model check. Instead, only a static consistency check (`audit_success_contract_consistency`) runs inside `finalize()`.
- **Consequence:** The model-led verify-repair loop is completely bypassed.

### Gap 2: Missing Success Contract Prompt Instruction
- **Design Spec:**
  The plan specifies that if `model_led_success_contract` is enabled and no contract is declared, `before_model_call` or orientation must inject a prompt instruction:
  ```text
  Before substantial work, declare a Success Contract from visible task/workspace evidence.
  Do not include hidden assumptions. You may revise it later only with cited visible evidence.
  ```
- **Actual Code:**
  No such instruction is ever injected. The solver is never prompted or guided to create a success contract.
- **Consequence:** Models will not declare success contracts unless they happen to do so by chance.

### Gap 3: Success Contract Obligation Finalization Blocking
- **Design Spec:**
  Unresolved `success_contract_missing` obligations should prevent `governed_pass` during finalization.
- **Actual Code:**
  There is no logic in `runner/kernel_gates.py` or `runner/active_evidence_kernel.py` to block finalization if `success_contract` is not declared.
- **Consequence:** Finalization accepts runs without a declared Success Contract.

### Gap 4: Context Pack Compaction uses Hard Truncation
- **Design Spec:**
  "Replace Hard Truncation With Adaptive Context Composition. Never slice serialized JSON with `compact[:6000]`."
- **Actual Code:**
  In `runner/kernel_context_pack.py` (`render_context_pack`):
  ```python
  def render_context_pack(context_pack: dict[str, Any]) -> str:
      compact = json.dumps(context_pack, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
      return compact if len(compact) <= 6000 else compact[:6000] + "…"
  ```
  This is a direct violation of the constitution. Slicing JSON causes syntax errors when the model attempts to parse it.
- **Consequence:** Hard truncation remains in place, producing malformed JSON outputs.

### Gap 5: Minor Naming Discrepancies
- **Design Spec:**
  Implementation plan calls for `validate_tool_call_against_schema`.
- **Actual Code:**
  Implemented as `validate_tool_arguments` in `runner/kernel_native_tools.py`. This is functionally equivalent but deviates from the design document's wording.

---

## 3. Corrective Plan

To bring the codebase in line with the design specifications, the following repairs must be implemented:
1. **Integrate Layer 2 verify-repair loop** into the `run_loop` of `runner/active_evidence_kernel.py`. Instead of breaking the loop immediately when the model claims done, run the Layer 2 Completion Auditor (up to 3 times) and feed the feedback back to the model if it returns `FAIL` or `UNCLEAR`.
2. **Inject the Success Contract obligation prompt** inside `runner/active_evidence_kernel.py` when `model_led_success_contract` is active and the contract has not been declared.
3. **Block `governed_pass`** when `success_contract_missing` is in `open_obligations`.
4. **Remove the `compact[:6000]` hard slicing** from `runner/kernel_context_pack.py` and replace it with a clean adaptive compaction strategy or simply omit slicing when under the model-led route where context limits are handled by compaction.

---

## 4. Conclusion & Verdict
The implementation **does not match the requirements** because the critical Layer 2 verify-repair loops and success contract prompting/blocking logic are either omitted or non-functional.

**Status:** **FAIL (Requires Repair)**
