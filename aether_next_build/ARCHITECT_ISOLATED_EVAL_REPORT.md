# ARCHITECT_ISOLATED_EVAL_REPORT

- generated_at: 2026-06-29T21:59:48
- primary_model: 5.4-mini high effort
- comparison_model: 5.3-codex high effort
- scope: isolated architect calls only; no solver/task attempts
- primary_tasks: filter-js-from-html, sparql-university, openssl-selfsigned-cert, regex-log, sqlite-db-truncate
- required_core_tasks: filter-js-from-html, sparql-university, openssl-selfsigned-cert

## Summary

- 5.4-mini primary after focused repair: 5/5 parseable; warnings=0; rejected_items=0; query_memory_available=5/5
- 5.3-codex comparison: 3/3 parseable; warnings=0; rejected_items=0; query_memory_available=3/3
- Initial 5.4-mini run had one real provider boundary failure on openssl-selfsigned-cert: incomplete response with no usable text due to max_output_tokens. A runner-only CLI control was added and the focused rerun with 32000 tokens produced a parseable config.
- No unsupported tools, unsupported context selectors, or rejected visible smoke specs appeared in the accepted 5.4-mini configs.
- Accepted configs kept query_memory available and used retrieval_augmented context with pending checks and/or active verifier findings.

## Primary 5.4-Mini Records

| task | parseable | score | tools | context | smokes | missing | notes |
|---|---:|---:|---|---|---:|---|---|
| filter-js-from-html | True | 9/10 | read_file, write_file, query_memory, inspect_checks, run_check | retrieval_augmented | 2 | solver_prompt_mentions_verify |  |
| sparql-university | True | 10/10 | read_file, write_file, query_memory, inspect_checks, run_check | retrieval_augmented | 0 | none |  |
| openssl-selfsigned-cert | True | 9/10 | read_file, write_file, query_memory, run_command, inspect_checks, run_check | retrieval_augmented | 4 | solver_prompt_mentions_verify | Focused 5.4-mini repair rerun with --max-output-tokens 32000 after initial max_output_tokens incomplete response. |
| regex-log | True | 9/10 | read_file, write_file, query_memory | retrieval_augmented | 0 | solver_prompt_mentions_verify |  |
| sqlite-db-truncate | True | 9/10 | inspect_artifact, read_file, run_command, write_file, query_memory, inspect_checks, run_check | retrieval_augmented | 2 | solver_prompt_mentions_verify |  |

## 5.3-Codex Comparison

| task | parseable | score | tools | context | missing |
|---|---:|---:|---|---|---|
| filter-js-from-html | True | 10/10 | read_file, write_file, query_memory | retrieval_augmented | none |
| sparql-university | True | 10/10 | read_file, write_file, query_memory | retrieval_augmented | none |
| openssl-selfsigned-cert | True | 10/10 | read_file, write_file, run_command, query_memory, inspect_checks, run_check | retrieval_augmented | none |

## Evidence Paths

- `architect_isolated_eval_54mini_20260629_214341/architect_only_eval.json`
- `architect_isolated_eval_54mini_openssl_repair_20260629_215629/architect_only_eval.json`
- `architect_isolated_eval_53codex_20260629_215103/architect_only_eval.json`
- `architect_isolated_eval_phase2_summary.json`
- `run_architect_only_eval.py`