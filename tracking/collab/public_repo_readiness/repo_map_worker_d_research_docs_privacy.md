# Repo Map Worker D: Research, Docs, Source Mirrors, and Publication Privacy

Scope inspected:

- `research/**` top-level and second-level, including `analysis`, `notes`, `source_finder_prompt_pack`, `sources`, `intake`, and `external`
- `blocks/**`
- `website/**`
- root `README.md` and related top-level docs
- `tracking/collab/stage_02_synthesis/**`
- `tracking/collab/public_repo_readiness/**`
- `research/sources/codebases/quarantine/**`
- root `LICENSE` / `NOTICE` status

## Executive Summary

The repo already has a credible public-facing spine, but it is mixed with raw mirrors, intake artifacts, and internal synthesis operations that should not ship as-is.

Best public material:

- the harness code and architecture surfaces in `blocks/`
- the public site source in `website/`
- curated research synthesis outputs, especially sanitized case studies and dossiers
- public methodology/docs that explain the harness and publication rules

Must stay private:

- raw intake bundles
- source mirrors under `research/sources/**`
- quarantined mirrors under `research/sources/codebases/quarantine/**`
- raw trajectories, eval captures, and ledger handoffs
- generated build artifacts and local caches

The biggest blockers to publication are:

- no root `LICENSE` or `NOTICE`
- many imported source mirrors with unresolved redistribution status
- several current docs still point at missing or internal-only publication surfaces
- raw research artifacts are not separated cleanly from curated outputs

The right move is to split the repository into:

1. public architecture/docs/case-study outputs
2. private raw source and intake stores
3. a documented provenance/redaction layer

## Inventory Table

| Path / group | What it contains now | Recommended class | Publication guidance |
|---|---|---|---|
| `README.md` | High-level repo entrypoint, but still broad and not publication-split | public architecture docs, after rewrite | Keep as the public landing page, but rewrite it to point to `docs/` and clearly separate public vs private surfaces. |
| `AGENTS.md` | Very detailed operator governance and private execution rules | needs decision, likely split | Split into public contributor guidance and private operator/governance notes. Do not publish the full current file as-is. |
| `blocks/` | Executable harness block library plus a short README | public architecture/code | Public core is fine. Keep generated caches out and consider a stronger public module index. |
| `website/` source files | Next.js marketing/public site source | public site | This is a genuine public site surface. Keep source, but exclude build output and vendored deps. |
| `website/.next/`, `website/node_modules/`, `website/.DS_Store`, `**/__pycache__` | Generated build/cache noise | generated/ignore | Never publish. These should stay ignored. |
| `website/src/app/*`, `website/src/components/*`, `website/public/*` | Public site implementation and assets | public site | Safe to publish as the web presentation layer. |
| `research/analysis/patterns.md`, `research/analysis/tool_calling_research_scan.md`, `research/analysis/bigai_trace_layer/README.md` | Curated synthesis notes and derived trace methodology | public curated research / public provenance-redaction docs | Good candidates for public research pages once source paths and private trace details are redacted. |
| `research/analysis/failure_modes.md` | Placeholder/TODO stub | generated/ignore or legacy/archive | Do not present as a finished public artifact until populated. |
| `research/analysis/bigai_trace_layer/output/**` | Derived event rows / indexes / query outputs | generated/ignore, or public provenance-redaction docs if sanitized | Keep raw outputs private. Only publish a redacted, source-safe derivative. |
| `research/source_finder_prompt_pack/` | Intake prompt pack, QC gates, merge protocol, runbook | public provenance-redaction docs, if sanitized | This can be public as methodology, but only if the prompts do not expose private intake assumptions or raw source content. |
| `research/notes/deepagent_locations.md` | Internal pointer map to committed corpus locations | private raw provenance note | Keep private. It is useful internally, but it is not a public-facing document. |
| `research/sources/papers/` | Paper PDFs, extracted text, metadata, review summaries | needs license/provenance decision | Full extracted text should stay private unless licensing is explicitly cleared. Summaries and citations may be public. |
| `research/sources/docs/` | Captured docs, HTML/text snapshots, capture metadata | private raw source mirror, with metadata possibly reusable | Keep raw captures private. A redacted index of sources can be public. |
| `research/sources/issues/` | Issue snapshots, artifacts, capture JSON | private raw source mirror | Keep private; use only sanitized summaries or citations in public docs. |
| `research/sources/informal/` | Blog/social/media captures and notes | needs license/provenance decision | Public redistribution is quote-limited and provenance-sensitive. Keep the raw mirror private and publish only curated summaries with links. |
| `research/sources/evals/` | Eval captures and artifacts | private raw source mirror / needs license-provenance decision | Keep raw eval captures private. Public docs should cite eval names and abstract the failure family, not redistribute raw captures. |
| `research/sources/codebases/` | Raw code mirrors of external projects | private raw source mirror | Do not publish the raw mirrors. Publish only curated architectural notes or short excerpts if licensing permits. |
| `research/sources/codebases/quarantine/` | High-risk mirrors, including leak/provenance-sensitive code | private raw source mirror / quarantine | Must remain private. This is explicitly a quarantine zone, not a public distribution surface. |
| `research/sources/trajectories/` | Raw run trajectories, task bundles, workspace outputs | private intake/raw trajectory dump | Keep private. Public output should be case-study summaries, not verbatim trajectories. |
| `research/external/symphony/` | External git clone with upstream LICENSE and `.git` history | needs license/provenance decision, private raw source mirror for now | Keep private until provenance and redistribution policy are finalized. Do not ship the clone wholesale. |
| `research/intake/**` | Raw bucket runs, normalized records, QC outputs, rejected items, manifests | private intake/raw trajectory/source dump | Private only. Public release should use only distilled summaries or exported reports. |
| `tracking/ledger/**` | Canonical historian ledger and raw inbox handoffs | private raw trajectory/source dump | Never publish verbatim. At most, export a redacted public summary. |
| `tracking/collab/public_repo_readiness/*.md` | Publication planning and curated repo-readiness reports | public provenance-redaction docs | These are good candidates for publication after minor cleanup. |
| `tracking/collab/stage_02_synthesis/trajectory_case_studies/*.md` | Concrete case studies linking runs to source/behavior | public case-study source | Strong public candidates. Redact exact task IDs, hidden answers, and private file paths before publishing. |
| `tracking/collab/stage_02_synthesis/source_system_dossiers/*.md` | Architectural-depth dossiers for source-visible systems | public curated research / public case-study source | Good public material after redaction. Keep caveats about quarantine and provenance visible. |
| `tracking/collab/stage_02_synthesis/eval_dossiers/*.md` | Eval contract and grader analysis | public curated research | Publish only the abstracted evaluation logic and redacted eval references. |
| `tracking/collab/stage_02_synthesis/mechanism_map/decision.md`, `failure_taxonomy/decision.md` | High-level synthesis judgments and carry-forward warnings | public curated research, if distilled | These are valuable public research summaries, but they should be exported as a clean public version rather than shipping the live internal decision files unchanged. |
| `tracking/collab/stage_02_synthesis/coverage_register/current_status.md` | Live coverage-control status | legacy/archive or private internal ops | Keep internal. It is useful for governance, but not a good public artifact. |
| `tracking/collab/stage_02_synthesis/deep_synthesis_plan/`, `deep_synthesis_setup/`, `deep_synthesis_wave_plan/`, `adjudication/`, `coverage_access/`, `eval_implications/`, `variant_family_seeds/`, `informal_cluster_dossiers/` | Active stage-02 planning, routing, and internal synthesis support | legacy/archive or private internal ops | Do not publish as-is. Export distilled conclusions only. |
| `runner/README.md` | Mixed current-surface and historical-reference guidance | public architecture docs, after rewrite | Rewrite to match the actual split between current public core and archive. |
| `research/README.md` | High-level research intake instructions | public provenance-redaction docs, after rewrite | Rewrite to explain the public/private boundary and the current research archive shape. |
| `blocks/README.md` | Block architecture overview | public architecture docs, after rewrite | Keep, but update the wording to reflect the real block taxonomy and any public/private split. |
| `website/README.md` | Generic Next.js scaffold README | public site docs, after rewrite | Replace boilerplate with repo-specific site instructions and a publication boundary note. |

## Recommended `docs/` Tree

`docs/` does not exist yet. It should become the public publication surface, with no raw intake or mirror data inside it.

Recommended structure:

```text
docs/
  README.md
  architecture/
    harness-overview.md
    blocks.md
    runner-archival-boundary.md
    website.md
  research/
    mechanism-map.md
    failure-taxonomy.md
    eval-dossiers.md
    patterns.md
    tool-calling-scan.md
  case-studies/
    headless-terminal.md
    db-wal-recovery.md
    git-multibranch.md
    prove-plus-comm.md
  provenance/
    source-inventory.md
    license-matrix.md
    redaction-policy.md
    third-party-notices.md
  publication/
    repo-publication-checklist.md
    public-private-boundary.md
```

Suggested content rules:

- `docs/architecture/` should describe the public harness and repo topology, not raw operator history.
- `docs/research/` should contain curated, redacted synthesis outputs only.
- `docs/case-studies/` should contain sanitized run narratives with no hidden answers, no private workspace dumps, and no exact eval secrets.
- `docs/provenance/` should document capture provenance, license status, and redaction policy.
- `docs/publication/` should tell future maintainers how to publish or refresh the public subset.

## Private / Ignore / Quarantine List

Keep these private or ignored:

- `research/intake/**`
- `tracking/ledger/**`
- `research/sources/trajectories/**`
- `research/sources/codebases/**`
- `research/sources/codebases/quarantine/**`
- `research/sources/evals/**`
- `research/sources/docs/**` raw captures
- `research/sources/issues/**` raw captures
- `research/sources/informal/**` raw captures
- `research/sources/papers/**` full extracted texts and PDFs unless licensing is cleared
- `research/external/symphony/`
- `website/.next/`
- `website/node_modules/`
- `.DS_Store`
- `**/__pycache__/`
- `*.pyc`

Also treat these as internal-only until a public export is prepared:

- `tracking/collab/stage_02_synthesis/deep_synthesis_plan/`
- `tracking/collab/stage_02_synthesis/deep_synthesis_setup/`
- `tracking/collab/stage_02_synthesis/deep_synthesis_wave_plan/`
- `tracking/collab/stage_02_synthesis/coverage_register/`
- `tracking/collab/stage_02_synthesis/coverage_access/`
- `tracking/collab/stage_02_synthesis/eval_implications/`
- `tracking/collab/stage_02_synthesis/variant_family_seeds/`
- `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/`

## License / Provenance Risks

1. Root `LICENSE` and `NOTICE` are missing.
2. The repo contains many mirrored upstream source trees, but there is no single publication-wide license reconciliation layer.
3. `research/sources/papers/` is particularly sensitive because full paper text redistribution can be licensing-problematic even when the papers are public to read.
4. `research/sources/informal/` includes social/media-style captures, which are citation- and quote-limit sensitive.
5. `research/sources/codebases/quarantine/claude-code_ts_release` and `research/sources/codebases/quarantine/claw-code` are explicitly high-risk mirrors and should stay quarantined.
6. `research/external/symphony/` is a live clone with upstream history; it needs a provenance and redistribution decision before any public release.
7. Raw eval and trajectory captures can reveal hidden tasks, verifier behavior, or private workspace state, so they should never be published verbatim.

Recommended provenance policy:

- every captured source should have a stable source URL or upstream commit
- every source mirror should record capture date, license, and redistribution status
- every public artifact should have a redaction note describing what was removed
- any uncertain source should default to private/quarantine until a decision is recorded

## Root Docs That Should Be Rewritten or Moved

Priority rewrite set:

1. `README.md`
2. `AGENTS.md`
3. `runner/README.md`
4. `research/README.md`
5. `blocks/README.md`
6. `website/README.md`

Secondary follow-up:

- `prompts/README.md`
- `evals/README.md`
- `experiments/README.md`
- `tasks/README.md`

What to change:

- remove boilerplate that describes missing or nonexistent directories
- clearly label what is public, what is private, and what is archived
- stop referencing internal-only folder shapes as if they are public docs
- move public-facing research narratives into `docs/`

## Open Questions

1. Should the public repo ship sanitized excerpts only, or should it also include redacted snapshots of selected source files?
2. Should `tracking/collab/public_repo_readiness/` remain a working area, or should its final outputs move into `docs/provenance/`?
3. What root license should govern the public repo?
4. Do we want a `NOTICE` file that aggregates third-party acknowledgments for all imported mirrors?
5. Should paper text mirrors remain entirely private, with only citation metadata published?
6. Which trajectory families are safe to publish as case studies after redaction, and which should stay internal because they are eval-contaminating or privacy-sensitive?
7. Do we want a dedicated public index for sanctioned source mirrors, or only curated summaries with links?

## Bottom Line

Publish:

- harness architecture
- curated research summaries
- sanitized case studies
- provenance/redaction policy docs

Keep private:

- raw intake
- raw mirrors
- trajectories
- quarantined code
- ledger handoffs
- build artifacts and caches

The repository is close to publication-ready only after the docs split, license decision, and provenance layer are made explicit.
