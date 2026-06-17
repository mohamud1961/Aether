# Local Capture Backfill Audit

Status: completed

Canonical output: `research/analysis/2026-03-31__accepted_corpus_local_capture_audit.md`

Reason for pointer-only file:

- The full audit was completed and stored under `research/analysis/` because it is a reusable analysis artifact.
- This file exists so the fresh-readiness run keeps a stable output path for prompt `06`.

Baseline audit summary

- Accepted sources audited: 103 before quarantine cleanup
- captured_and_linked: 2
- not_captured: 79
- malformed_or_suspicious: 22

Post-repair snapshot

- 22 malformed or suspicious accepted IDs quarantined from the accepted corpus
- accepted corpus size after quarantine: 81
- linked accepted records after first-wave backfill: 8
- remaining accepted records without linkage after this pass: 73

Next actions

- Use the canonical audit file for the detailed repair plan.
- Treat this file as the stable handoff pointer for the fresh-readiness workflow.
