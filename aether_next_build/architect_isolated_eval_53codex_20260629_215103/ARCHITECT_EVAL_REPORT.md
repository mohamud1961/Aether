# Architect-Only Eval Report

Scope: old ContractArchitect vs Runtime Workbench Architect on official task prompts/workspace maps.
Official test/grader excerpts are saved as review context only; they are not sent to the architect model.

| task | old score | workbench score | workbench missing |
|---|---:|---:|---|
| filter-js-from-html | 7/8 | 10/10 | none |
| sparql-university | 7/8 | 10/10 | none |
| openssl-selfsigned-cert | 7/8 | 10/10 | none |

## Notes

### filter-js-from-html

- Old missing: architect_designed_solver_prompt
- Workbench missing: none
- Solver role: You are implementing a minimal-diff, verification-first HTML JavaScript stripping utility.
- Workflow: Inspect relevant inputs / Build or modify artifact / Self-check / Submit when ready
- Self-verification: Confirm /app/filter.py reads argv[1] and writes back to the same file path (in-place behavior). / Ensure sanitizer removes clear JavaScript vectors (e.g., script blocks, inline on* handlers, javascript: URLs) while preserving non-dangerous HTML text/structure. / Ensure approach does not parse and reformat full HTML output; unchanged content should remain unchanged except harmful substrings removed. / Run inspect_checks, then run_check on available check ids; resolve failures before submit. / Verify only intended file changes are present and no unrelated workspace edits were made.
- Memory use: Call query_memory before re-reading files already inspected to avoid redundant reads. / Call query_memory before overwriting /app/filter.py to compare against prior failed attempts/findings. / After any failed check, query_memory for failure details before editing again.

### sparql-university

- Old missing: architect_designed_solver_prompt
- Workbench missing: none
- Solver role: Task-focused SPARQL author and verifier for an RDF university knowledge graph
- Workflow: inspect relevant inputs / build or modify artifact / self-check / submit when ready
- Self-verification: Confirm the query uses ontology terms found in `/app/university_graph.ttl` (no guessed predicates/classes). / Verify full-professor filtering is explicit and tied to the graph’s rank/title representation. / Verify EU-country filtering uses the correct 27 ISO codes as of 2025-08-16 and only for current workplaces. / Verify at least one worked-in department satisfies `> 10` enrolled students in classes taught in that same department (department-scoped counting, distinct students). / Verify final projection is exactly `?professorName` and grouped distinct `?country` list via `GROUP_CONCAT`.
- Memory use: Call `query_memory` before re-reading `university_graph.ttl` to avoid duplicate extraction work. / Call `query_memory` before overwriting `/app/solution.sparql` to reuse prior findings/diffs. / Call `query_memory` after any failed check/finding to target the next edit.

### openssl-selfsigned-cert

- Old missing: architect_designed_solver_prompt
- Workbench missing: none
- Solver role: You are a TLS provisioning engineer focused on reproducible OpenSSL artifact creation and evidence-backed verification.
- Workflow: Inspect current workspace and query_memory for prior attempts/findings before creating or overwriting files / Generate TLS artifacts with OpenSSL and create the Python verification script at the exact required paths / Run command-based self-checks plus inspect_checks/run_check for available harness checks / Submit only after evidence confirms file presence, permissions, certificate fields, and script success output
- Self-verification: Confirm /app/ssl exists and includes server.key, server.crt, server.pem, verification.txt / Confirm server.key permission is 600 / Use OpenSSL to verify subject includes O=DevOps Team and CN=dev-internal.company.local / Use OpenSSL to verify certificate dates and SHA-256 fingerprint, and ensure verification.txt records subject, validity dates, and fingerprint / Confirm server.pem contains both private key and certificate blocks / Run python3 /app/check_cert.py and confirm it prints CN, expiration date in YYYY-MM-DD format, and 'Certificate verification successful' / Call inspect_checks and run_check for any available checks before final submission
- Memory use: Call query_memory before repeating failed OpenSSL generation/verification attempts / Call query_memory before re-reading large outputs already captured / Call query_memory before overwriting existing artifacts to avoid undoing a previously valid state
