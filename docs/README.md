# Aether documentation

This directory is intentionally small. It describes the **current** Aether research system and public funding programme.

## Start here

1. [`GETTING_STARTED.md`](GETTING_STARTED.md) — install, deterministic qualification and production-surface checks.
2. [`ARCHITECTURE.md`](ARCHITECTURE.md) — what the model owns, what Aether owns, and what stays external.
3. [`EVIDENCE_PIPELINE.md`](EVIDENCE_PIPELINE.md) — how live runs become trajectories, run records, hashes, observability and public evidence.
4. [`SAFETY_BOUNDARY.md`](SAFETY_BOUNDARY.md) — bounded execution, permissions, isolation, evidence and what is not yet proven.
5. [`QUALIFICATION.md`](QUALIFICATION.md) — deterministic public qualification and production-surface checks.
6. [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) — current performance, evidence, reproducibility and publication limits.
7. [`DEVELOPMENT_HISTORY.md`](DEVELOPMENT_HISTORY.md) — the nine-month development path and the transition from historical HarnessEng/Aether-2 work to current Aether.
8. [`RESEARCH_PROGRAMME.md`](RESEARCH_PROGRAMME.md) — the proposed three-month matched evaluation programme.
9. [`../evidence/README.md`](../evidence/README.md) — selected cases, held-out negative evidence and public evidence rules.
10. [`../evidence/MANIFEST.json`](../evidence/MANIFEST.json) — machine-readable evidence index.

## Historical documents

The repository's Git history contains earlier architecture, eval-suite, workflow and research documents from the HarnessEng/Aether-2 phase. They are intentionally not kept in the current root because they describe systems that are no longer the production Aether architecture.

The top-level `research/` directory is retained as an explicitly historical archive because it demonstrates the investigation path that led to the current runtime. It is not current architecture authority.

The top-level `tracking/` directory contains frozen verification/provenance authorities. It is not current runtime authority.

When a historical artifact remains important to a present claim, it is promoted into `evidence/` with explicit provenance and caveats rather than left as ambiguous current documentation.
