# Architect-Only Eval Report

Scope: old ContractArchitect vs Runtime Workbench Architect on official task prompts/workspace maps.
Official test/grader excerpts are saved as review context only; they are not sent to the architect model.

| task | old score | workbench score | workbench missing |
|---|---:|---:|---|
| openssl-selfsigned-cert | 7/8 | 9/10 | solver_prompt_mentions_verify |

## Notes

### openssl-selfsigned-cert

- Old missing: architect_designed_solver_prompt
- Workbench missing: solver_prompt_mentions_verify
- Solver role: Verification-first OpenSSL certificate builder
- Workflow: Inspect /app/Dockerfile and any existing cert-related artifacts before writing anything, and use memory if a path was already read. / Use run_command with OpenSSL to generate the key/cert/PEM and the verification text with explicit subject fields and 365-day validity, then write the Python checker. / Call inspect_checks once, run only relevant checks, and avoid repeating passed checks unless dependent files changed. / Submit only when file content, permissions, and checker output all satisfy the spec.
- Self-verification: server.key exists, is a 2048-bit RSA private key, and has mode 600. / server.crt is self-signed for O=DevOps Team and CN=dev-internal.company.local with 365 days validity. / server.pem contains both the private key and certificate and can be parsed. / verification.txt contains the cert subject, validity dates, and SHA-256 fingerprint from the generated cert. / check_cert.py loads /app/ssl/server.crt, prints the Common Name and expiration date in YYYY-MM-DD format, and ends with Certificate verification successful.
- Memory use: Call query_memory before rereading any path that was already inspected. / Call query_memory before overwriting /app/ssl files or /app/check_cert.py. / Call query_memory after a failed parse/check to recover prior evidence and avoid repeating a known-bad action. / Use query_memory to retrieve prior hashes, excerpts, and changed-file history.
