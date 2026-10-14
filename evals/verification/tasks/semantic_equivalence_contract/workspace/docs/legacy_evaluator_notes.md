# Legacy evaluator notes (pre-1.0)

- All operators share one left-to-right level, so `2+3*4` is evaluated as `(2+3)*4`.
- Results are truncated to 32 bits.
- Leading zeros are rejected.

These notes describe the old loader code. Treat them as stale; the spec in `spec/` is current.
