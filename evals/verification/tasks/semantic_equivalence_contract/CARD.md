# Task card: semantic_equivalence_contract (v2)

Admission: **debug**. The grader executes the candidate on the host, and isolated grading is not yet qualified.
Reference, known-bad and careless controls test this v2 design.

## Design (v2)

- Goal-level ticket: a deploy-config loader's evaluator gives wrong answers, and a replacement is needed.
- Stale sources disagree with the contract: a withdrawn 0.3 draft (right-associative `-`), legacy notes (one
  level, 32-bit wrap, leading zeros rejected), a legacy table (`10-3-2` as 9) and old logs (32-bit result).
- The visible check keeps its three smoke cases. The grader adds fixed edge cases and 150 generated expressions
  whose expected values come from Python's `ast`, with a sealed seed.
- Byte identity of spec, notes, table, logs and checker.

## Controls

- Known-bad: 7 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| missing_solution_module | careless do_nothing, wrong_target |
| expression_result_mismatch | known_bad hardcoded_constants, left_to_right_ignores_precedence, right_recursive_subtraction, int32_wrap, returns_float; careless fake_it, skip_check |
| expression_evaluation_error | known_bad parentheses_unsupported, leading_zero_rejected; careless half_done |
| expression_evaluation_timeout | guard only |
| evidence_file_modified | guard only |
