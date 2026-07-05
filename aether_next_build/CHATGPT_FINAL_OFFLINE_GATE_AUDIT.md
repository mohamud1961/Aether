# ChatGPT Final Offline Gate Audit

Date: 2026-06-29

## Purpose

Add the remaining high-value deterministic gate while Codex/model usage is blocked: an offline validator for verifier-only experiment bundles. This gives Codex a hard acceptance gate after it runs `run_verifier_only_eval.py --mode model`.

## Implemented

- Added `validate_verifier_only_eval.py`.
- Fixed a harmless duplicate `case` key in `run_verifier_only_eval.py` row assembly.
- Extended integration tests to cover the validator.

## Validator Behaviour

The validator checks a verifier-only output bundle without calling a model, solver, Docker, VM, benchmark, board, or official grader.

It requires:

- expected five verifier-only cases:
  - `semantic_wrong`
  - `missing_artifact`
  - `schema_mismatch`
  - `repeated_no_progress`
  - `insufficient_evidence`
- per-case artifact files:
  - `verifier_packet.json`
  - `raw_output.json`
  - `parsed_result.json`
  - `active_findings_after.json`
  - `judgement.json`
- packet fields:
  - `task_prompt`
  - `success_definition`
  - `local_verification_limits`
  - `artifact_evidence`
  - `artifact_history`
  - `memory_events`
  - `recent_receipts`
  - `reason`
- parse success;
- `evidence_bound == true`;
- `actionable == true`;
- case-specific verdict expectations:
  - first four cases should be `needs_repair` with active findings;
  - `insufficient_evidence` should be `uncertain_missing_evidence`;
- basic secret-leak scan over output files.

## Commands Run

```text
python3 -m pytest -q tests/test_chatgpt_integration_scenarios.py
6 passed in 8.07s
```

```text
python3 -m pytest -q --ignore=tests/test_docker_runner.py
188 passed in 11.56s
```

```text
python3 -m compileall -q aether_next
passed
```

```text
python3 run_verifier_only_eval.py --mode fake --out-dir /mnt/data/final_pass_validator_fake
passed
```

```text
python3 validate_verifier_only_eval.py /mnt/data/final_pass_validator_fake --report /mnt/data/final_pass_validator_report.md
ok=true
```

## Result

The deterministic local harness is now at a clean handoff point. Remaining near-term work is model-side verifier-only experimentation using this validator as the acceptance gate.

## Codex Next Gate

Run:

```text
python3 run_verifier_only_eval.py --mode model --out-dir verifier_only_eval_54mini_<STAMP>
python3 validate_verifier_only_eval.py verifier_only_eval_54mini_<STAMP> --report VERIFIER_ONLY_54MINI_VALIDATION.md
```

If validation fails, do not continue to solver/replay. Inspect raw outputs and parser/judgement failures first.
