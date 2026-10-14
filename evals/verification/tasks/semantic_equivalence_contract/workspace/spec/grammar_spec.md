# Expression grammar specification (version 1.2)

## Grammar

```
expr    := term (('+' | '-') term)*
term    := factor ('*' factor)*
factor  := '(' expr ')' | INTEGER
INTEGER := [0-9]+
```

## Precedence

- `*` binds tighter than `+` and `-`.
- `+` and `-` have equal precedence.

## Associativity

- All binary operators are left-associative.
- `10-3-2` evaluates as `(10-3)-2 = 5`.

## Values

- Integers are decimal. Leading zeros are accepted and do not change the value (`007` is 7).
- Results are exact. Intermediate and final values are not limited to any machine width.

## Input

- Expressions contain only digits, `+`, `-`, `*`, `(` and `)`, with no whitespace.

## Return type

- `evaluate(expr: str) -> int`, always a Python `int`.

## Examples

- `1+2` -> `3`
- `2+3*4` -> `14`
- `(2+3)*4` -> `20`
- `10-3-2` -> `5`
- `007+1` -> `8`

## Changelog

- 1.2: leading zeros accepted; exact large results stated explicitly.
- 1.1: parentheses may wrap any `expr`, including a lone term.

## Superseded

- Draft 0.3 made `-` right-associative. That draft was withdrawn and is not implemented.
