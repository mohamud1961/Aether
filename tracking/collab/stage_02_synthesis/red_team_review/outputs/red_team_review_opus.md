# RED_TEAM_REVIEW_OUTPUT (Antigravity)

- scope: Full adversarial review of the research-to-synthesis-prep pipeline, from source-finder prompt design through intake, dedup, QC, capture backfill, corpus demotions, eval metadata repair, frozen synthetic-prep manifests, AND research depth/scale/coverage.
- review_date: 2026-04-01
- reviewer_role: red-team reviewer under principal routing

---

## Pipeline Findings

Findings are ordered by severity: critical → high → medium → low.

---

### Finding 1 — Mock/Fabricated Canonical URLs in Accepted Records

- **severity**: critical
- **title**: Six accepted source records contain mock or fabricated canonical URLs that cannot resolve to real artifacts
- **repo_evidence_paths**:
  - `research/intake/records/src_pap_e5f6a1b2c3d4.json` — `https://arxiv.org/abs/reponavigator_mock`
  - `research/intake/records/src_pap_1a2b3c4d5e6f.json` — `https://arxiv.org/abs/infoqa_mock`
  - `research/intake/records/src_pap_5e6f1a2b3c4d.json` — `https://arxiv.org/abs/trm_mock`
  - `research/intake/records/src_pap_b2c3d4e5f6a1.json` — `https://arxiv.org/abs/simpletool_mock`
  - `research/intake/records/src_pap_d4e5f6a1b2c3.json` — `https://arxiv.org/abs/gap_benchmark_mock`
  - `research/intake/records/src_trc_1a3b5c7d9e2f.json` — `https://traces.example.org/analysis/stop-policy-failure`
- **direct_observation**: grep of all 288 accepted records for `_mock` and `example.org`/`example.com` URL fragments returns 6 matches. All 6 are in the deduped manifest, 5 are in the blocked-exceptions list, 1 (`src_trc_1a3b5c7d9e2f`) is in the blocked-exceptions list with a different reason. All 6 have `artifact_relpath` empty. None can be opened or verified.
- **why_it_matters**: These records contaminate provenance trust. If synthesis touches any of these source IDs, it will cite evidence that does not exist. The `_mock` suffix strongly suggests they were generated as placeholder IDs during source-finder runs and were never replaced with real URLs. Source-finder prompt design guards against weak sources but has no guard against fabricated identity. The QC gate checked schema validity but did not check URL plausibility.
- **minimum_fix**: Demote all 6 mock-URL records out of the accepted corpus into `rejected/` with a clear `demotion_reason`. Update `corpus__deduped.json`, all affected bucket manifests, and `corpus__captured_for_synthetic_prep.json`. Add a QC gate rule that rejects any canonical_url containing `_mock`, `example.com`, `example.org`, or `placeholder`.

---

### Finding 2 — QC Report Status Is `fail` and the Failure Is Unresolved

- **severity**: high
- **title**: The latest QC report (`2026-04-01__qc_report.json`) has status `fail` with an unresolved accepted-corpus consistency failure
- **repo_evidence_paths**:
  - `research/intake/normalized/qc/2026-04-01__qc_report.json` (line 2: `"status": "fail"`, lines 306-311: failure detail)
- **direct_observation**: The QC report records one failure under gate `accepted_corpus_consistency`: the frozen accepted manifest (288 IDs) no longer matches dedup pass_03's `normalized_records` (280 IDs). The 8 manifest-only IDs are the 8 sources backfilled by the eval metadata repair pass. The eval metadata repair pass added these IDs to the manifests and records dir but did not re-run dedup pass_03 to reconcile it.
- **why_it_matters**: The project is about to freeze a synthesis-prep corpus on top of a QC report that says "fail". Even though the 8 sources are legitimate backfills, leaving the QC gate in a failed state undermines the pipeline's own integrity guarantee.
- **minimum_fix**: Either re-run dedup pass_03 to include the 8 new sources (making it pass_04), or add the 8 sources to pass_03's `normalized_records` and re-run QC to produce a passing report.

---

### Finding 3 — `src_cod_564b05dcc95b` (RALPH Loop) Has Dual Membership

- **severity**: high
- **title**: RALPH Loop source appears in both the captured synthesis-prep manifest AND the current-blocked list simultaneously
- **repo_evidence_paths**:
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json` (line 14)
  - `research/intake/rejected/2026-04-01__current_blocked_accepted_sources.json` (lines 19-25)
  - `research/intake/normalized/qc/2026-04-01__qc_report.json` (line 318)
- **direct_observation**: `src_cod_564b05dcc95b` is the only source ID that appears in `current_blocked_accepted_sources.json` but is NOT in `accepted_blocked_exceptions.json`. It IS in the captured manifest. The `current_blocked` file was not updated after this source was successfully captured.
- **why_it_matters**: Creates a contradiction that any downstream pipeline consumer will interpret incorrectly.
- **minimum_fix**: Remove `src_cod_564b05dcc95b` from `2026-04-01__current_blocked_accepted_sources.json`.

---

### Finding 4 — 41 Accepted Sources Have No Local Artifact

- **severity**: high
- **title**: 14.2% of the accepted corpus (41 of 288) has no `artifact_relpath` and exists only as metadata records with no openable local capture
- **repo_evidence_paths**:
  - `research/intake/rejected/2026-04-01__accepted_blocked_exceptions.json` (41 entries)
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json` (line 4: `accepted_source_count: 288`)
  - Programmatic check: 41 of 288 records return empty `artifact_relpath`
- **direct_observation**: The deduped manifest lists 288 "accepted" source IDs. The captured manifest lists 247 captured IDs and 41 are explicitly blocked. Every blocked exception has `block_reason: "capture.json missing"`. Their records contain metadata but no openable content.
- **why_it_matters**: Synthesis consumers who see "288 accepted sources" will assume 288 openable evidence artifacts. In reality, only 247 are openable. If synthesis cites these sources by "reading" them, it will silently hallucinate content not present in the repo.
- **minimum_fix**: Ensure synthesis-facing documentation clearly distinguishes "288 accepted records" from "247 openable artifacts". Synthesis instructions must explicitly prohibit reading or citing any source in the blocked-exceptions list as if its content were locally available.

---

### Finding 5 — Source-Finder Template Has Stale Time Window

- **severity**: medium
- **title**: The canonical source-finder template specifies a primary window ending 2026-03-25, which is now 7 days stale
- **repo_evidence_paths**:
  - `research/source_finder_prompt_pack/prompts/canonical_source_finder_template.md` (lines 21-22)
- **direct_observation**: Line 22 reads `Primary window: 2025-11-24 through 2026-03-25`. Current date is 2026-04-01.
- **why_it_matters**: Drift risk for the next intake wave. Not a current defect for frozen corpus.
- **minimum_fix**: Update the primary window end date before the next intake wave.

---

### Finding 6 — Evidence Inventory Output Has Not Been Produced

- **severity**: medium
- **title**: The evidence inventory brief exists but its output artifact has not been produced
- **repo_evidence_paths**:
  - `tracking/collab/stage_02_synthesis/evidence_inventory/brief.md` (task packet referencing `outputs/organizer.md`)
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/README.md` (placeholder)
- **direct_observation**: The file `organizer.md` does not exist. Synthesis has no structured guide to evidence prioritization.
- **why_it_matters**: Without the evidence inventory output, synthesis will make ad-hoc prioritization decisions.
- **minimum_fix**: Produce the evidence inventory organizer before deep synthesis, or explicitly decide to skip it.

---

## Research Depth, Scale, and Coverage Findings

---

### Finding 7 — 82 Locally Captured Sources Have No Intake Record

- **severity**: high
- **title**: 82 genuinely unindexed source captures in `research/sources/` — the 288-record index covers only 72% of local evidence
- **repo_evidence_paths**:
  - `research/sources/papers/` (166 dirs vs ~96 paper records)
  - `research/sources/docs/` (101 dirs vs ~78 doc records)
  - Programmatic diff of `research/sources/*/src_*` IDs against `research/intake/records/*.json`
- **direct_observation**: 371 `src_*` directories exist under `research/sources/`. Only 288 are in intake records. Of the 83 unindexed, 1 is a known quarantine, leaving **82 truly unindexed** — 69 papers (with PDFs and capture.json) and 13 docs (with captures). None are in any demotion or rejection list.
- **why_it_matters**: Synthesis reading only intake records will systematically miss 82 locally captured sources.
- **minimum_fix**: Backfill intake records for unindexed captures, or explicitly ensure synthesis reads from `research/sources/` directly.

---

### Finding 8 — 102 Informal Sources Are Completely Unindexed

- **severity**: high
- **title**: Zero intake records reference any of the 102 informal markdown captures
- **repo_evidence_paths**:
  - `research/sources/informal/` (102 `.md` files)
  - `research/intake/inbox/informal_links.md` (link list only)
  - `tracking/collab/stage_02_synthesis/evidence_inventory/brief.md` — explicitly says "treat informal evidence as a mandatory evidence class, not an optional appendix"
- **direct_observation**: 102 markdown captures covering Cursor, Codex, Claude Code, Devin, and many other topics. Zero intake records reference them. Not assigned to any bucket, not deduped, not QC-checked.
- **why_it_matters**: The project's own design docs say informal evidence is mandatory, not optional. Despite this, the pipeline has completely excluded it from the indexed corpus.
- **minimum_fix**: At minimum, instruct synthesis to scan `research/sources/informal/` alongside intake records.

---

### Finding 9 — Mechanism Tags Are Hyper-Fragmented

- **severity**: medium
- **title**: 1,135 unique mechanism tags and 641 unique failure-mode tags across 288 records
- **repo_evidence_paths**: Programmatic analysis of all records' `mechanism_tags` and `failure_mode_tags` fields
- **direct_observation**: Most frequent mechanism tag (`tools_x_context`) appears only 11 times. Most frequent failure-mode tag (`false_completion`, `context_bloat`) appears only 8 times. The vast majority appear once.
- **why_it_matters**: No natural clustering exists. Synthesis cannot aggregate by tag without producing hundreds of singleton categories.
- **minimum_fix**: Create a normalization layer mapping to 20-40 mechanism families, or instruct synthesis to work from `claim_snippets` text directly.

---

### Finding 10 — The Analysis Layer Is Functionally Empty

- **severity**: medium
- **title**: No synthesis or analysis has been performed on the corpus
- **repo_evidence_paths**:
  - `research/analysis/failure_modes.md` (3 lines, TODO stub)
  - `research/analysis/patterns.md` (27 lines, 5 seed entries)
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/` (README placeholder only)
- **direct_observation**: `failure_modes.md` is a TODO. `patterns.md` has 5 manually entered patterns. No mechanism map, no failure taxonomy, no cross-source synthesis exists.
- **why_it_matters**: Scale ≠ depth. The corpus is wide but unprocessed. Synthesis starts from raw materials.
- **minimum_fix**: Acknowledge that synthesis starts from raw corpus. The evidence inventory organizer should be the first output.

---

### Finding 11 — Browser/GUI Coverage Is Structurally Thin

- **severity**: low
- **title**: Only 15 of 288 records tag `browser_agent` vs 141 `terminal_agent`
- **repo_evidence_paths**: Task regime analysis across all records
- **direct_observation**: WebArena family only represented by WebArena-Infinity. Acceptable for terminal-first project.
- **minimum_fix**: Flag as known coverage gap in synthesis instructions.

---

## Self-Corrections After Stress-Testing

After the initial findings, I stress-tested my own claims. Two findings were overstated:

### ❌ Originally Overstated: Thin Bucket Severity

I initially said artifact_workspace (1 record) and memory (4 records) are "dangerously thin." This was misleading because I ignored `bucket_secondary` coverage:

| Bucket | Primary | Secondary | True Total |
|--------|---------|-----------|------------|
| artifact_workspace | 1 | 11 | **12** |
| memory | 4 | 7 | **11** |
| observability_audit | 7 | 19 | **26** |

Additionally, the quality gate explicitly says *"Sparse buckets are allowed to stay sparse; padding with weak sources is a failure."* The thinness may be by design.

### ❌ Originally Misleading: "67% Assertion-Heavy" Framing

The 67% overall assertion rate is skewed by source type. Per-type breakdown:

| Source Type | Claims | Measured % |
|-------------|--------|------------|
| paper | 222 | **42%** |
| benchmark_site | 7 | **71%** |
| postmortem | 1 | **100%** |
| issue_thread | 154 | 18% |
| engineering_writeup | 110 | 17% |
| official_doc | 218 | 5% |

Papers are 42% measured — totally reasonable. The assertion dominance comes from official docs (5% measured), which is *expected*. This is not a corpus deficiency.

---

## Confirmed Strengths

1. **Manifest arithmetic is clean.** Records on disk (288) = deduped manifest IDs (288) = bucket-summed IDs (288). Captured (247) + blocked (41) = 288. No orphans.
2. **Demoted sources fully excluded.** All 16 demoted IDs absent from all active manifests.
3. **Quarantined duplicate handled correctly.** `src_pap_dd4ca3841fb4` properly quarantined with matching PDF hash evidence.
4. **Capture repair was disciplined.** 7 commit-pinned, 18 not forced through. Demotions for unrecoverable sources.
5. **Schema consistency.** No schema regressions across 288 records.
6. **Eval metadata repair was conservative.** 9 backfills from local captures, not from inference.
7. **Dedup decisions traceable.** Two decision files with dates.
8. **Cross-bucket linkage is decent.** 178/288 (62%) have `bucket_secondary`.
9. **Raw scale is genuinely strong.** 508+ local source artifacts, 267 trajectory task dirs, 1,773+ codebase mirror files across 5 major codebases.
10. **Trajectory corpus is first-class evidence.** 3 implementations × 89 shared tasks.
11. **Codebase mirrors are substantial.** KIRA (656 files), deepagents (525), langchain (293).
12. **Source type diversity is reasonable.** 95 papers, 78 docs, 56 issues, 42 writeups, 9 repos, 5 benchmarks.
13. **Recency is strong.** 90% in primary window. Average recency 4.75/5.

---

## Residual Risks If Proceeding Now

1. **False citation risk** from 6 fabricated-URL records.
2. **QC confidence gap** — latest report says `fail`.
3. **"288 accepted" overstates openable evidence** — only 247 exist locally.
4. **Synthesis on intake metadata alone misses ~28% of local evidence** and 100% of informal evidence.
5. **Hyper-fragmented tag vocabulary** makes automated clustering impractical.
6. **Zero intermediate analysis** — synthesis starts from raw corpus.
7. **`current_blocked_accepted_sources.json` is stale** — includes a successfully captured source.

---

## Must Fix Before Deep Synthesis

| # | Finding | Minimum Action |
|---|---------|---------------|
| 1 | Mock/fabricated URLs | Demote all 6, add QC gate for URL plausibility |
| 2 | QC report `fail` | Re-run dedup + QC to produce a passing report |
| 3 | RALPH Loop dual membership | Remove from `current_blocked_accepted_sources.json` |

---

## Should Address Before or During Deep Synthesis

| # | Finding | Action |
|---|---------|--------|
| 7 | 82 unindexed source captures | Backfill records or instruct synthesis to scan `research/sources/` directly |
| 8 | 102 unindexed informal sources | Instruct synthesis to scan `research/sources/informal/` |
| 9 | Tag fragmentation | Normalize tags or instruct synthesis to use raw claim text |

---

## Safe to Proceed Judgment

**Not yet safe to proceed** until the 3 must-fix items are resolved (estimated: 1-2 hours).

Once those are fixed, the corpus is structurally sound for synthesis, provided synthesis instructions explicitly account for:
- Reading `research/sources/` and `research/sources/informal/` beyond just intake records
- Not citing blocked-exception sources as if their content were locally available
- Working from `claim_snippets` text rather than hyper-fragmented mechanism tags

---

## Recommended Next Hand-Off Target

Hand off to the **principal project steward** with three actions:
1. Execute the 3 must-fix items.
2. Re-run QC to produce a `pass` status report.
3. Update synthesis team spec to account for the should-address items.
4. Then hand the corpus to the **deep synthesis lead** for Stage 2A.
