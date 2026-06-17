# Worker B: Recovery Command/Path Serialization

## Scope

- `runner/kernel_artifacts.py`
- `runner/kernel_recovery.py`
- `runner/kernel_state.py`
- `runner/active_evidence_kernel.py`
- `tests/test_kernel_artifacts.py`
- `tests/test_active_evidence_kernel.py`

## Root Cause

- Raw heredoc command text was being mined too aggressively for path hints.
- Those command fragments could flow into artifact registry refreshes and required-artifact checks, where `Path(...)` and filesystem existence checks were applied to text that was really shell code.
- Recovery signatures also embedded the full command string, which made recovery cards overly large and mixed command text into fields that should stay bounded.

## Changes

- Added `extract_artifact_path_refs` in `runner/kernel_artifacts.py` and used it for command-to-path extraction.
- Hardened artifact record creation so unsafe command text becomes a bounded placeholder instead of reaching path resolution or existence checks.
- Updated artifact registry refresh and required-artifact validation to skip or safely label invalid path refs before any filesystem access.
- Switched `runner/kernel_state.py` and `runner/active_evidence_kernel.py` to the safer command-path extractor.
- Replaced raw-command recovery signatures in `runner/kernel_recovery.py` with a bounded command fingerprint plus a short preview snippet.

## Tests Run

- `python3 -m py_compile runner/kernel_artifacts.py runner/kernel_state.py runner/kernel_recovery.py runner/active_evidence_kernel.py tests/test_kernel_artifacts.py tests/test_active_evidence_kernel.py`
- `python3 -m pytest -q tests/test_kernel_artifacts.py tests/test_active_evidence_kernel.py`
- Result: `50 passed`

## Residual Risks

- The command-path extractor is intentionally conservative, so unusual path spellings or paths with spaces may be missed.
- Unsafe required-artifact inputs now fail with a bounded placeholder label instead of crashing, which is safer but may still need follow-up if a future lane intentionally exercises unusual path syntax.
