# Verifier/Grader Alignment Board

Rows: 10

## Confusion Matrix

| Verifier bucket | Grader pass | Grader fail | Grader unavailable |
| --- | ---: | ---: | ---: |
| clean | 1 | 1 | 0 |
| not_clean | 0 | 7 | 0 |
| invalid | 0 | 0 | 1 |

## Alignment Status Counts

- aligned: 8
- not_applicable: 1
- verifier_false_clean: 1

## Invalid Row Counts

- grader_unavailable: 1

## Rows

| Task | Verifier | Grader | Alignment | Status | Trace |
| --- | --- | --- | --- | --- | --- |
| filter-js-from-html | clean | fail | verifier_false_clean | completed |  |
| sparql-university | not_clean | fail | aligned | incomplete |  |
| openssl-selfsigned-cert | not_clean | fail | aligned | error |  |
| filter-js-from-html | not_clean | fail | aligned | incomplete |  |
| filter-js-from-html | invalid | unavailable | not_applicable | incomplete |  |
| sparql-university | not_clean | fail | aligned | incomplete |  |
| openssl-selfsigned-cert | not_clean | fail | aligned | incomplete |  |
| filter-js-from-html | not_clean | fail | aligned | incomplete | /home/azureuser/harnesseng_vm/aether_next_build/vm_goal_runs/20260703T145841Z_canonical_aether_fresh_stage1_vm_exportenv/traces/filter-js-from-html.trace.json |
| sparql-university | not_clean | fail | aligned | incomplete | /home/azureuser/harnesseng_vm/aether_next_build/vm_goal_runs/20260703T145841Z_canonical_aether_fresh_stage1_vm_exportenv/traces/sparql-university.trace.json |
| openssl-selfsigned-cert | clean | pass | aligned | completed | /home/azureuser/harnesseng_vm/aether_next_build/vm_goal_runs/20260703T145841Z_canonical_aether_fresh_stage1_vm_exportenv/traces/openssl-selfsigned-cert.trace.json |
