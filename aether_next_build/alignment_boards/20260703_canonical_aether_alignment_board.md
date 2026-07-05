# Verifier/Grader Alignment Board

Rows: 7

## Confusion Matrix

| Verifier bucket | Grader pass | Grader fail | Grader unavailable |
| --- | ---: | ---: | ---: |
| clean | 0 | 1 | 0 |
| not_clean | 0 | 5 | 0 |
| invalid | 0 | 0 | 1 |

## Alignment Status Counts

- aligned: 5
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
