# Architect-Only Eval Report

Scope: old ContractArchitect vs Runtime Workbench Architect on official task prompts/workspace maps.
Official test/grader excerpts are saved as review context only; they are not sent to the architect model.

| task | old score | overall | solver | verifier | config | key missing |
|---|---:|---:|---:|---:|---:|---|
| filter-js-from-html | 0/8 | 10.0/10 | 10/10 | 10/10 | 10/10 | none |
| sparql-university | 0/8 | 10.0/10 | 10/10 | 10/10 | 10/10 | none |
| openssl-selfsigned-cert | 0/8 | 10.0/10 | 10/10 | 10/10 | 10/10 | none |

## Notes

### filter-js-from-html

- Old missing: parseable TaskContract
- Overall: 10.0/10
- Solver prompt: 10/10 missing=none
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 530
- Verifier prompt words: 402
- Solver role: Verification-first Python sanitizer engineer for a byte-preserving HTML XSS filter.
- Verifier role: Adversarial read-only auditor for /app/filter.py in a byte-preserving HTML sanitization task.
- Workflow: Inspect workspace state and interpreter availability first; if python is absent but python3 is present, use python3 for any probes and local checks. / Create /app/filter.py as a single CLI script that reads argv[1], rewrites that file in place, and removes JavaScript with narrow text edits instead of parsing and reserializing the DOM. / Preserve unchanged bytes, whitespace, line endings, tag order, and non-dangerous attributes; target only harmful substrings such as script blocks, inline event handlers, and javascript: URLs when they appear. / Run a Python syntax check on /app/filter.py and then run a small ad hoc HTML sample through the script to confirm the file is modified in place and formatting outside removed content is unchanged. / If a local check fails or the verifier later reports needs_repair, repair the named artifact or gap, rerun the exact failing validation on the updated file, and resubmit only after fresh evidence shows the issue is fixed.
- Self-verification: Confirm /app/filter.py exists and is valid Python before any semantic claim. / Confirm the script uses argv[1] and opens the same file for read/modify/write so the original HTML file is updated in place. / Use a tiny sample HTML file with tables, headers, spacing, and safe attributes to verify the output differs only by the intended harmful removals and that no pretty-printing, attribute reordering, or whitespace normalization occurred. / Check that the sanitizer does not depend on unavailable modules or install steps and does not write a separate output file.
- Evidence requirements: The solver must produce /app/filter.py in the workspace. / The solver must show a successful Python syntax check for /app/filter.py. / The solver must run at least one representative local sample that demonstrates in-place mutation and preservation of harmless formatting. / The solver must retain evidence that the chosen sanitizer strategy targets JavaScript without reserializing the whole document.
- False-positive risks: Using an HTML parser or serializer that changes formatting while still removing JavaScript. / Removing only script tags while missing inline handlers, javascript: URLs, or other attack surfaces. / Writing a new file or stdout output instead of modifying argv[1] in place. / Passing syntax checks but failing to preserve whitespace, line endings, or attribute order on real HTML.
- Minimum completion evidence: /app/filter.py exists and is valid Python. / A local sample proves the script edits the target HTML file in place. / The sample evidence shows harmless HTML is unchanged except for the removed harmful substrings. / No evidence suggests DOM reserialization or other formatting churn.

### sparql-university

- Old missing: parseable TaskContract
- Overall: 10.0/10
- Solver prompt: 10/10 missing=none
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 514
- Verifier prompt words: 445
- Solver role: SPARQL query author and verifier for a university knowledge graph.
- Verifier role: Adversarial read-only verifier for a SPARQL query artifact.
- Workflow: Read /app/university_graph.ttl first and identify the exact prefixes, classes, and predicates for professor rank, department membership, university location, student enrollment, class teaching, and any date fields. / Draft the query in /app/solution.sparql using only ontology terms observed in the Turtle file, with the required projection `SELECT ?professorName (GROUP_CONCAT(DISTINCT ?country; separator=", ") AS ?countries)` and a GROUP BY on ?professorName. / Use 2025-08-16 as the reference date wherever temporal filtering is needed, and ensure the query distinguishes current employment/enrollment from historical records if the graph models dates. / Re-read /app/solution.sparql after writing it and, if run_command is available together with a local SPARQL parser/CLI, syntax-check the file; otherwise perform a careful content audit against the Turtle source. / If a local check fails or a later verifier finding says needs_repair, repair the named clause in /app/solution.sparql, rerun the relevant validation, and resubmit only after the gap is actually fixed.
- Self-verification: Confirm that /app/solution.sparql exists, is non-empty, and contains a single SPARQL SELECT query with the exact requested projection and GROUP BY. / Confirm that the query body visibly encodes all three constraints: full professor status, at least one qualifying EU-country department, and at least one department with more than 10 currently enrolled students in classes taught there. / Confirm that any temporal logic uses the 2025-08-16 reference date and that the query does not rely on guessed predicates, placeholder text, or extra output variables. / If you repeat a read or write because automatic memory surfaced prior evidence, use the surfaced excerpt or diff, narrow the inspection, or justify why the repeat is necessary instead of blindly redoing the same broad step.
- Evidence requirements: Create /app/solution.sparql with one SPARQL query that can be read back from disk. / Show the exact requested projection and GROUP BY in the file content. / Demonstrate, in the file content, all three required filters: full professor, EU-country work relation, and >10 currently enrolled students in classes taught by at least one worked-in department. / Use the 2025-08-16 reference date wherever the query needs temporal reasoning.
- False-positive risks: A file can exist yet contain a placeholder or incomplete query. / A query can look structurally right while using guessed predicates not supported by the Turtle file. / A query can satisfy the country aggregation syntax while failing the department/student-count semantics. / A query can be tied to historical rather than current employment or enrollment and still look plausible at a glance.
- Minimum completion evidence: /app/solution.sparql exists and is non-empty. / A read-back shows the exact SELECT projection and GROUP_CONCAT DISTINCT country aggregation. / A read-back shows clauses for full-professor status, EU-country employment, and the >10-students-per-department condition. / No obvious placeholder text or guessed ontology names remain in the query.

### openssl-selfsigned-cert

- Old missing: parseable TaskContract
- Overall: 10.0/10
- Solver prompt: 10/10 missing=none
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 545
- Verifier prompt words: 387
- Solver role: OpenSSL certificate build-and-verify agent for local TLS artifacts
- Verifier role: Adversarial read-only auditor for local TLS certificate artifacts
- Workflow: Inspect the workspace first, then probe actual availability of openssl and python/python3 before writing files; if python is absent but python3 is present, standardize on python3 for the checker and validation. / Create /app/ssl, generate /app/ssl/server.key as a 2048-bit RSA private key with mode 600, and generate /app/ssl/server.crt as a self-signed certificate valid for 365 days with Organization Name DevOps Team and Common Name dev-internal.company.local. / Assemble /app/ssl/server.pem so it contains both the private key and the certificate in PEM form, then derive /app/ssl/verification.txt from the actual generated certificate by recording its subject, validity dates, and SHA-256 fingerprint. / Write /app/check_cert.py using only Python standard-library modules so it verifies the certificate exists, loads it, prints the Common Name and expiration date in YYYY-MM-DD format, and emits the success line only after all checks pass. / Run the strongest safe local validations available, compare outputs against the task requirements, and if any check fails repair the named artifact or command input, rerun the relevant validation, and resubmit only after the mismatch is fixed.
- Self-verification: Confirm /app/ssl/server.key is present, readable only by the owner, and passes an OpenSSL private-key integrity check or equivalent permission/stat inspection. / Confirm /app/ssl/server.crt reports the required subject, a 365-day validity window, and the expected SHA-256 fingerprint directly from the generated certificate, not from a manual transcription. / Confirm /app/ssl/server.pem contains both BEGIN PRIVATE KEY and BEGIN CERTIFICATE blocks and is not missing either half of the bundle. / Run /app/check_cert.py with python or python3 and verify it loads the certificate, prints the Common Name and YYYY-MM-DD expiration date, and ends with Certificate verification successful; if a local check fails or the verifier returns needs_repair, inspect the named artifact, change the workspace state, rerun the specific validation, and do not resubmit until fresh evidence shows the repair worked.
- Evidence requirements: An OpenSSL readback of /app/ssl/server.crt showing the certificate subject, notBefore/notAfter dates, and SHA-256 fingerprint from the generated certificate. / A permission readback for /app/ssl/server.key proving mode 600. / A successful run of /app/check_cert.py showing the Common Name, the expiration date in YYYY-MM-DD format, and Certificate verification successful. / Content evidence that /app/ssl/server.pem contains both the private key and certificate PEM sections.
- False-positive risks: The certificate files exist but the subject or common name is wrong or incomplete. / The key file is present but not actually protected with permission mode 600. / verification.txt contains the right-looking metadata but not from the current generated certificate. / The Python checker is syntactically valid but only simulates success instead of loading the certificate.
- Minimum completion evidence: All required files exist and are nonempty. / server.key is confirmed to be mode 600. / server.crt is confirmed to carry the exact required subject and validity. / /app/check_cert.py runs successfully and prints the success message.
