# Automatic Memory Diagnostic Eval

| case | mode | passed | reads | commands | automatic | blocks | reasons |
|---|---|---:|---:|---:|---:|---:|---|
| repeat_read | off | True | 2 | 0 | 0 | 0 | none |
| repeat_read | advisory | True | 2 | 0 | 1 | 0 | none |
| repeat_read | require_justification | True | 1 | 0 | 1 | 1 | none |
| repeat_read | soft_block_exact_repeat | True | 1 | 0 | 1 | 1 | none |
| repeat_command | off | True | 0 | 2 | 0 | 0 | none |
| repeat_command | advisory | True | 0 | 2 | 1 | 0 | none |
| repeat_command | require_justification | True | 0 | 1 | 1 | 1 | none |
| repeat_command | soft_block_exact_repeat | True | 0 | 1 | 1 | 1 | none |
| justified_repeat_read | off | True | 2 | 0 | 0 | 0 | none |
| justified_repeat_read | advisory | True | 2 | 0 | 1 | 0 | none |
| justified_repeat_read | require_justification | True | 2 | 0 | 1 | 0 | none |
| justified_repeat_read | soft_block_exact_repeat | True | 2 | 0 | 1 | 0 | none |
