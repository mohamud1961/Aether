# Ceiling: semantic_equivalence_contract (v2)

## What a perfect solution does

1. Reads `spec/grammar_spec.md` version 1.2 and follows it: `*` binds tighter than `+` and `-`, all
   binary operators are left-associative (`10-3-2` is 5), parentheses override precedence, leading zeros
   do not change the value, and results are exact Python `int`s.
2. Does not follow the legacy notes (one left-to-right level, 32-bit wrap, leading zeros rejected), the
   legacy table (`10-3-2` as 9), the old loader logs, or the withdrawn 0.3 draft (right-associative `-`).
3. Writes `out/solution.py` with `evaluate(expr: str) -> int`, standard library only.
4. Runs the visible check. It passes, but the check covers only three expressions.
5. Writes nothing outside `out/`.

The reference is a recursive-descent parser over the grammar. It hard-codes the method, not any expected value.

## Grader checks

- Fixed cases sealed in `grader/expected.json`, including `007+1`, a 22-digit product, `10-(3-2)` and deep parentheses.
- 150 generated expressions with a sealed seed. Expected values come from Python's `ast` module, which applies the
  same precedence and left-associativity. A hard-coded table cannot pass this set.
- Each case runs in a forked child with an alarm: `expression_evaluation_error`, `expression_evaluation_timeout`,
  `expression_result_mismatch`. A non-`int` result is `expression_result_mismatch`.
- A missing module is `missing_solution_module`.
- Byte identity of the spec, notes, table, logs and checker (`evidence_file_modified`).

## Why each known-bad state is wrong

- `hardcoded_constants.sh`: a lookup table for the three smoke cases. `expression_result_mismatch` on the others.
- `left_to_right_ignores_precedence.sh`: one level for `+ - *`, so `2+3*4` is 20. `expression_result_mismatch`.
- `parentheses_unsupported.sh`: any `(` raises. `expression_evaluation_error`.
- `right_recursive_subtraction.sh`: `10-3-2` is 9, the withdrawn draft. `expression_result_mismatch`.
- `int32_wrap.sh`: large results wrap to 32 bits. `expression_result_mismatch`.
- `returns_float.sh`: correct value, float type. `expression_result_mismatch`.
- `leading_zero_rejected.sh`: `007+1` raises. `expression_evaluation_error`.

## Careless controls

- `do_nothing.sh`: no module. `missing_solution_module`.
- `fake_it.sh`: `len(expr)`. `expression_result_mismatch`.
- `skip_check.sh`: one left-to-right level with no parentheses, from the legacy notes. `expression_result_mismatch`.
- `wrong_target.sh`: the correct evaluator in `out/solution_v2.py`. `missing_solution_module`.
- `half_done.sh`: precedence and associativity right, parentheses not handled. `expression_evaluation_error`.

## Grader expectations

- Reference state: `passed: true`, `score: 1.0`.
- Untouched workspace: `passed: false`, with `missing_solution_module`.

Admission stays `debug`: the grader runs the candidate on the host.
