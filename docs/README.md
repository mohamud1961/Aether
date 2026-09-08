# Aether documentation

This directory is intentionally small. It describes the **current** Aether research system and public funding programme.

## Start here

1. [`GETTING_STARTED.md`](GETTING_STARTED.md) — shallow clone, install, deterministic qualification and production-surface checks.
2. [`ARCHITECTURE.md`](ARCHITECTURE.md) — what the model owns, what Aether owns, and what stays external.
3. [`RUNTIME_SURFACE.md`](RUNTIME_SURFACE.md) — canonical entrypoints, machine-measured import graph, dynamic bridge exceptions and current/historical naming boundary.
4. [`EVIDENCE_PIPELINE.md`](EVIDENCE_PIPELINE.md) — what each live run records and how evidence reaches the public repository.
5. [`SAFETY_BOUNDARY.md`](SAFETY_BOUNDARY.md) — bounded execution, permissions, isolation, evidence and what is not yet proven.
6. [`QUALIFICATION.md`](QUALIFICATION.md) — live GitHub qualification, exact environment receipts and production-surface checks.
7. [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) — current empirical/reproducibility limitations stated explicitly.
8. [`DEVELOPMENT_HISTORY.md`](DEVELOPMENT_HISTORY.md) — the nine-month development path and the transition from historical HarnessEng/Aether-2 work to current Aether.
9. [`RESEARCH_PROGRAMME.md`](RESEARCH_PROGRAMME.md) — the proposed three-month matched evaluation programme.
10. [`../evidence/README.md`](../evidence/README.md) — selected cases, held-out negative evidence and public evidence rules.

## Historical documents

The repository's Git history contains earlier architecture, eval-suite, workflow and research documents from the HarnessEng/Aether-2 phase. They are intentionally not kept in the current root because they describe systems that are no longer the production Aether architecture.

The top-level `research/` directory is retained as an explicitly historical archive because it demonstrates the investigation path that led to the current runtime. It is not current architecture authority.

The public Git history is substantially larger than the present tracked release tree. Ordinary reviewers should use the shallow-clone path in [`GETTING_STARTED.md`](GETTING_STARTED.md); full history is needed only when investigating development lineage.

When a historical artifact remains important to a present claim, it is promoted into `evidence/` with explicit provenance and caveats rather than left as ambiguous current documentation.
