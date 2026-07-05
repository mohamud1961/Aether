# NARROW_REAL_TASK_REPORT

- generated_at: 2026-06-30T00:26:42
- scope: exact approved tasks only: filter-js-from-html, sparql-university, openssl-selfsigned-cert
- architect_mode: workbench
- run_config: effort=low, max_steps=8, run_timeout_s=30
- status: completed_with_failures
- note: this is real row evidence after Docker/image preload; it is not a performance win

## Result Rows

| task | status | reward | classifier | confidence | step | reconfigs | grader | receipts |
|---|---|---:|---|---|---:|---:|---|---:|
| filter-js-from-html | incomplete | 0.0 | model_limit | medium | 8 | 1 | grader_timeout_after_30s | 6 |
| sparql-university | incomplete | 0.0 | harness_context_failure | low | 8 | 0 | grader_timeout_after_30s | 3 |
| openssl-selfsigned-cert | incomplete | 0.0 | harness_context_failure | medium | 8 | 1 | grader_timeout_after_30s | 8 |

## Classification Notes

### filter-js-from-html

- classifier_detail: genuine progress and diverse actions but no passing check
- model_parse_errors: []
- recent_receipts:
  - config:realization / config_realization / success=True / compiled architect config realization
  - a1:query / query_memory / success=True / memory query 'prior reads, file history, or failure notes for /app/filter.': 0 matches
  - a1:read / read_file / success=False / file not found: filter.py
  - a2:write / write_file / success=True / wrote filter.py
  - reconfig-0:invalid / reconfigure_validation / success=False / reconfiguration invalid: missing_bootstrap_substrate; missing_helper_tool_substrate
  - a2:read / read_file / success=True / read filter.py (1091 bytes)

### sparql-university

- classifier_detail: insufficient evidence to attribute to model; harness did not surface a real attempt
- model_parse_errors: []
- recent_receipts:
  - config:realization / config_realization / success=True / compiled architect config realization
  - a1:query / query_memory / success=True / memory query 'prior reads or receipts for /app/university_graph.ttl and an': 0 matches
  - a2:read / read_file / success=True / read university_graph.ttl (10169 bytes)

### openssl-selfsigned-cert

- classifier_detail: repeated identical failures with no state change
- model_parse_errors: []
- recent_receipts:
  - config:realization / config_realization / success=True / compiled architect config realization
  - a1:query / query_memory / success=True / memory query 'Prior observations, file reads, command results, or artifact': 0 matches
  - a2:read / read_file / success=False / file not found: ssl/server.key
  - a3:read / read_file / success=False / file not found: ssl/server.crt
  - a4:read / read_file / success=False / file not found: check_cert.py
  - reconfig-0:invalid / reconfigure_validation / success=False / reconfiguration invalid: missing_bootstrap_substrate; missing_helper_tool_substrate
  - act-1:query / query_memory / success=True / memory query 'Current known state for /app, especially any prior reads or ': 4 matches
  - a2:experiment / experiment / success=True / experiment : exit=0

## Evidence Paths

- `narrow_real_task_results_20260630_001742.json`
- `narrow_real_task_traces_20260630_001742/filter-js-from-html.trace.json`
- `narrow_real_task_traces_20260630_001742/sparql-university.trace.json`
- `narrow_real_task_traces_20260630_001742/openssl-selfsigned-cert.trace.json`
- `narrow_real_task_snapshots_20260630_001742/`