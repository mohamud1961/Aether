# Automatic Memory Diagnostic Eval

| case | mode | passed | reads | commands | automatic | blocks | reasons |
|---|---|---:|---:|---:|---:|---:|---|
| repeat_read | off | True | 2 | 0 | 0 | 0 | none |
| repeat_read | advisory | False | 2 | 0 | 1 | 0 | context_missing_automatic_memory_findings |
| repeat_read | require_justification | False | 1 | 0 | 1 | 1 | context_missing_automatic_memory_findings |
| repeat_read | soft_block_exact_repeat | False | 1 | 0 | 1 | 1 | context_missing_automatic_memory_findings |
| repeat_command | off | True | 0 | 2 | 0 | 0 | none |
| repeat_command | advisory | False | 0 | 2 | 1 | 0 | context_missing_automatic_memory_findings |
| repeat_command | require_justification | False | 0 | 1 | 1 | 1 | context_missing_automatic_memory_findings |
| repeat_command | soft_block_exact_repeat | False | 0 | 1 | 1 | 1 | context_missing_automatic_memory_findings |
| justified_repeat_read | off | True | 2 | 0 | 0 | 0 | none |
| justified_repeat_read | advisory | False | 2 | 0 | 1 | 0 | context_missing_automatic_memory_findings |
| justified_repeat_read | require_justification | False | 2 | 0 | 1 | 0 | context_missing_automatic_memory_findings |
| justified_repeat_read | soft_block_exact_repeat | False | 2 | 0 | 1 | 0 | context_missing_automatic_memory_findings |
