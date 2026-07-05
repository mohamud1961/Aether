# Architect-Only Eval Report

Scope: old ContractArchitect vs Runtime Workbench Architect on official task prompts/workspace maps.
Official test/grader excerpts are saved as review context only; they are not sent to the architect model.

| task | old score | workbench score | workbench missing |
|---|---:|---:|---|
| filter-js-from-html | 6/8 | 9/10 | solver_prompt_mentions_verify |
| sparql-university | 6/8 | 10/10 | none |
| openssl-selfsigned-cert | 7/8 | 0/10 | parseable HarnessConfigIR |
| regex-log | 6/8 | 9/10 | solver_prompt_mentions_verify |
| sqlite-db-truncate | 7/8 | 9/10 | solver_prompt_mentions_verify |

## Notes

### filter-js-from-html

- Old missing: verification_or_schema_signal, architect_designed_solver_prompt
- Workbench missing: solver_prompt_mentions_verify
- Solver role: verification-first Python artifact builder for a minimally invasive HTML JavaScript scrubber
- Workflow: Inspect /app/Dockerfile and query_memory for any prior reads, writes, hashes, or failures before touching /app/filter.py; do not re-read unchanged files. / Build or modify /app/filter.py using the smallest standard-library change set that preserves raw HTML formatting and avoids serializer-style rewrites. / After editing, inspect the file content and run harness-owned checks: call inspect_checks once to discover available check IDs, then run_check only for relevant visible checks; do not repeat passing checks. / Submit only after the file path, argv[1] handling, in-place write behavior, and minimal-change HTML preservation are all confirmed by direct inspection plus available checks.
- Self-verification: Confirm the script is exactly at /app/filter.py and is valid Python syntax. / Confirm it reads argv[1], opens that path, and writes the transformed result back to the same file. / Confirm the implementation avoids broad HTML reformatting, pretty-printing, or whitespace normalization. / Confirm only JavaScript-dangerous content is removed and non-dangerous HTML structure/attributes remain intact. / If any check fails, query_memory before re-reading or re-running the same check; use the failure history instead of guessing.
- Memory use: Call query_memory before repeating a read of /app/Dockerfile or /app/filter.py. / Call query_memory before overwriting /app/filter.py to avoid clobbering newer work. / Call query_memory after any failure or failed check to retrieve prior findings, file history, and failure clusters. / Do not repeat reads or checks when memory shows the file or result is unchanged.

### sparql-university

- Old missing: verification_or_schema_signal, architect_designed_solver_prompt
- Workbench missing: none
- Solver role: Verification-first SPARQL query author for a university knowledge graph; inspect the Turtle file for the actual ontology terms, then encode the required query in /app/solution.sparql and verify the file before submitting.
- Workflow: inspect relevant inputs in /app/university_graph.ttl, especially prefixes, classes, predicates, and current-state/date patterns / build or modify /app/solution.sparql with the SPARQL query / self-check syntax, projection, grouping, and current-date logic; query memory before repeating work / submit when ready only after the file is complete and no unresolved failure evidence remains
- Self-verification: Confirm the query uses the graph's real classes/predicates for professor, department, university, country, teaching, enrollment, and currentness before writing the file. / Confirm qualification logic is separated from the returned country aggregation so ?countries includes all current work countries for each qualifying professor, not just EU countries. / Confirm the query keeps the 2025-08-16 reference date consistent wherever current-state filtering is needed and that the projection is exactly ?professorName with GROUP_CONCAT(DISTINCT ?country; separator=", ") AS ?countries. / If harness-owned checks are visible, inspect them first and run only the relevant one after the file changes; do not rerun unchanged checks or reread unchanged files without a query_memory lookup first.
- Memory use: Call query_memory before rereading /app/university_graph.ttl or /app/solution.sparql, before overwriting /app/solution.sparql, and after any failed check to recover prior excerpts, hashes, observations, or failure clusters. / Use query_memory to avoid repeating the same read or check when the file and hypothesis have not changed.

### openssl-selfsigned-cert

- Old missing: architect_designed_solver_prompt
- Workbench missing: parseable HarnessConfigIR
- Errors: old=[] workbench=["background job resp_0c5091a01d88aec8006a42d9ce31408197a089a1e90a7a222a incomplete with no usable text: IncompleteDetails(reason='max_output_tokens')"]

### regex-log

- Old missing: verification_or_schema_signal, architect_designed_solver_prompt
- Workbench missing: solver_prompt_mentions_verify
- Solver role: Regex artifact solver and verifier.
- Workflow: Inspect the task prompt first; if you are resuming an attempt, query memory before rereading or overwriting /app/regex.txt. / Build or modify the artifact by writing only the regex text to /app/regex.txt, keeping it compatible with Python re.MULTILINE and re.findall. / Self-check the candidate against the required edge cases: IPv4 validity, date ranges including February 29, alphanumeric boundaries, and the last-date-per-line rule. / Submit when ready only after a clean read-back and no unresolved ambiguity about capture groups or line-level behavior; if check tools are exposed in this runtime, use them only after writing the file and before submit.
- Self-verification: The pattern is valid Python regex syntax and produces the intended findall result. / No date or IPv4 token is allowed to be immediately preceded or followed by an alphanumeric character. / IPv4 octets are decimal and do not permit leading zeros. / The date logic covers valid YYYY-MM-DD ranges and permits February 29 in all years. / A line with multiple dates yields only the last date as the match.
- Memory use: Call query_memory before rereading /app/regex.txt or any prior attempt. / Call query_memory before overwriting the file. / Call query_memory after a failed self-check to retrieve prior failure clusters and observations.

### sqlite-db-truncate

- Old missing: architect_designed_solver_prompt
- Workbench missing: solver_prompt_mentions_verify
- Solver role: Forensic SQLite recovery solver
- Workflow: Inspect the damaged database first with binary-aware artifact inspection and query memory before repeating any prior investigation. / Recover source-backed rows into /app/recover.json, preserving exact word/value pairs and omitting any uncertain guesses. / Self-check the written file with available harness checks and JSON/content validation before considering submission. / Submit only after the file is stable, structurally correct, and no unresolved verification issue remains.
- Self-verification: Confirm /app/recover.json exists and parses as a JSON array. / Confirm every element has exactly the keys word and value, with word as a string and value as an integer. / Confirm each included row is backed by recovered database evidence; do not invent missing rows or pad the result. / Call inspect_checks once to discover harness-owned checks, then run any relevant check ids after writing the file.
- Memory use: Call query_memory before re-reading trunc.db or overwriting recover.json so repeated work and prior findings can be avoided. / Call query_memory after a failed inspection or check to recover the current failure cluster, prior hashes/excerpts, and any learned recovery observations.
