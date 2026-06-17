# Lego Blocks

Each subdirectory is a **dimension** of harness design. Each file within is a **variant** for that dimension.

All variants within a dimension must implement the same interface so they can be freely swapped.

## Rules

- Each file < 200 lines
- No cross-block dependencies (a context block must not import from execution)
- Every block must be testable in isolation
