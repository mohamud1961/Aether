# Raw Ledger Update

- recorded_at_utc: 2026-06-17T12:12:47.186731+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Antigravity
- task: fix-public-readiness-and-provenance-sweep
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: ee56b5064dd3b10aacd18c2a8b71ed4c7d4d0adc3bb652c3f3ae57a81e013eff
- commit_message: "chore: clean up quarantined provenance wording, expand sweep scope, and align public docs/tests"
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-17/121247_antigravity_fix-public-readiness-and-provenance-sweep_ee56b5064d.md

```text
RAW_LEDGER_UPDATE
- actor: Antigravity
- task: fix-public-readiness-and-provenance-sweep
- event_type: implementation
- summary: Cleaned up quarantined provenance wording in active package files, expanded the cold start sweep scope, and aligned architectural docs, case studies, and public tests.
- observations: Provenance check script only checked a small allowlist and missed five active package files containing 'quarantined/adaptation' phrases. The architecture doc misstated agents/hooks/skills subpackages as stubbed/navigation-only. The manifest smoke case study pointed to dead paths. The Makefile/CI only executed a subset of public tests.
- inference: A dynamic file search (using git ls-files) ensures the provenance sweep covers the full package. Documenting agents/hooks/skills as canonical matches their active status. Adding the missing tests to the Makefile enforces the full reviewer guarantee.
- evidence_paths: aether/agents/loader.py, aether/hooks/lifecycle.py, aether/hooks/registry.py, aether/tools/README.md, aether/tools/mcp.py, scripts/public_readiness_cold_start.sh, docs/architecture/public-architecture.md, docs/case-studies/public-manifest-repair-smoke.md, docs/publication/public_readiness.md, Makefile
- affected_components: aether, scripts, docs, Makefile
- decision_change: Scan all package files instead of a hardcoded list; run all public readiness tests in Makefile.
- unresolved_questions: None
- confidence: high
- commit_message: "chore: clean up quarantined provenance wording, expand sweep scope, and align public docs/tests"
```
