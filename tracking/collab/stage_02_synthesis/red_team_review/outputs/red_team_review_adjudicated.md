ADJUDICATED_RED_TEAM_REVIEW

## Frozen Ground Truth Used For Adjudication

- `research/intake/normalized/qc/2026-04-01__qc_report.json` is the current QC ground truth and is a `pass`.
- The current deduped accepted layer is `288` source IDs in `research/intake/normalized/manifests/corpus__deduped.json`.
- The current deep-synthesis capture layer is `247` source IDs in `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`.
- The current explicit blocked-exception layer is `41` source IDs in `research/intake/rejected/2026-04-01__accepted_blocked_exceptions.json`.
- `2026-04-01__current_blocked_accepted_sources.json` is not the live blocked/captured partition; it is a stale snapshot.
- The Terminal-Bench duplicate quarantine remains out of active synthesis scope in `research/intake/rejected/2026-04-01__synthesis_duplicate_quarantine.json`.

## Findings

### 1. Stage 2A scope is still not closed for deep synthesis

- status: `confirmed_live`
- severity: `critical`
- title: Missing evidence organizer plus out-of-intake evidence coverage still leaves first-wave synthesis scope ambiguous
- which_reviews_raised_it: `Codex`, `Opus`
- current_repo_evidence_paths:
  - `tracking/collab/stage_02_synthesis/evidence_inventory/brief.md`
  - `tracking/collab/stage_02_synthesis/evidence_inventory/decision.md`
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/README.md`
  - `SYNTHESIS_TEAM_SPEC.md`
  - `research/intake/normalized/manifests/corpus__deduped.json`
  - `research/sources/papers/`
  - `research/sources/docs/`
  - `research/sources/informal/`
  - `research/sources/trajectories/`
- adjudication: This remains live. The Stage 2A evidence-inventory artifact still requires `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`, but only `outputs/README.md` exists. The synthesis-stage docs still say evidence inventory should come before deep synthesis and that informal evidence stays in scope. Repo-local comparison against the current accepted and rejected manifests also still shows a governance gap beyond the frozen intake layer: there are zero accepted records whose `artifact_relpath` points into `research/sources/trajectories/` or `research/sources/informal/`, and there are still 75 captured `src_*` directories under `research/sources/papers/` and `research/sources/docs/` that are not represented in the current accepted or rejected intake manifests. Codex and Opus were directionally right that the intake layer is not coterminous with the strongest repo-local evidence, even though their earlier count of omitted captured dirs is now overstated.
- why_it_matters_now: The project still lacks a current, written answer to “what exactly is in first-wave deep synthesis scope?” Without that scoping artifact, a synthesis agent either ignores mandatory evidence classes or improvises a second unguided evidence path.
- minimum_fix_or_operating_rule: Before deep synthesis, either write the missing `organizer.md` with explicit routing rules for trajectories, informal evidence, and out-of-intake captures, or issue an explicit principal scoping note that first-wave synthesis is limited to `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json` and that all other evidence classes are deferred intentionally.

### 2. Six mock or fabricated canonical URLs still survive in the accepted corpus

- status: `confirmed_live`
- severity: `critical`
- title: False-provenance placeholder records are still present in the accepted layer
- which_reviews_raised_it: `Codex`, `Opus`
- current_repo_evidence_paths:
  - `research/intake/records/src_pap_1a2b3c4d5e6f.json`
  - `research/intake/records/src_pap_5e6f1a2b3c4d.json`
  - `research/intake/records/src_pap_b2c3d4e5f6a1.json`
  - `research/intake/records/src_pap_d4e5f6a1b2c3.json`
  - `research/intake/records/src_pap_e5f6a1b2c3d4.json`
  - `research/intake/records/src_trc_1a3b5c7d9e2f.json`
  - `research/intake/normalized/manifests/corpus__deduped.json`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - `research/intake/rejected/2026-04-01__accepted_blocked_exceptions.json`
  - `research/intake/normalized/qc/2026-04-01__qc_report.json`
- adjudication: This remains live. The same six records still carry `_mock` or `example.org` canonical URLs, still remain in `corpus__deduped.json`, and still sit inside the blocked-exception layer. They do not leak into `corpus__captured_for_synthetic_prep.json`, so they are not part of the 247 active captured synthesis inputs, but they still contaminate the broader accepted corpus and the QC pass did not reject them.
- why_it_matters_now: This is still a corpus-integrity defect. Any workflow that reads “accepted corpus” instead of the captured synthesis manifest can still encounter obviously noncanonical source identities.
- minimum_fix_or_operating_rule: Deep synthesis must not read from `corpus__deduped.json` as if all 288 accepted records were usable evidence. Use `corpus__captured_for_synthetic_prep.json` as the active source set, treat the full blocked-exception list as out of scope for evidence-bearing synthesis, and then demote or replace the six placeholder records in a later corpus-hygiene slice.

### 3. The documented enum contract is still out of sync with accepted records, but the “full schema failure” framing was too broad

- status: `confirmed_live`
- severity: `high`
- title: Enum drift against the shared schema/template is real, even though normalized records are also documented to add extra fields
- which_reviews_raised_it: `Codex`, `Opus`
- current_repo_evidence_paths:
  - `research/source_finder_prompt_pack/shared_json_schema.json`
  - `research/source_finder_prompt_pack/prompts/canonical_source_finder_template.md`
  - `research/source_finder_prompt_pack/repo_output_plan.md`
  - `research/intake/records/src_doc_86dfad9d959c.json`
  - `research/intake/records/src_doc_ded84a79b0f5.json`
  - `research/intake/records/src_iss_89b2c3d4e5f1.json`
  - `research/intake/records/src_pap_163afe88846b.json`
  - `research/intake/normalized/qc/2026-04-01__qc_report.json`
- adjudication: Codex was directionally right and Opus was too strong in the opposite direction. A repo-local comparison against the enums documented in `shared_json_schema.json` and `canonical_source_finder_template.md` still finds 19 accepted records using off-contract values across `artifact_type`, `decision_targets`, `task_regime`, and `environment_type`. Sample live values include `SEP`, `blog_post`, `discussion`, `preprint`, `step_verification`, `human_in_the_loop`, `termination`, `long_running_task`, `software_engineering_agent`, `any`, `dockerized_harness`, and `formal_simulator`. However, Codex overstated the schema critique when treating the shared schema as the entire normalized-record contract: `repo_output_plan.md` explicitly documents normalized records adding fields like `artifact_relpath`, so extra normalized fields are not themselves regressions.
- why_it_matters_now: Anything that filters or aggregates accepted records using the shared enum vocabulary can still silently misclassify or drop valid records. The current QC warning saying “No schema regressions were detected” is narrower than the enum mismatch a human reader sees in the documented template/schema pair.
- minimum_fix_or_operating_rule: Do not use strict enum-based automation over accepted records until the project either ratifies the expanded vocabulary across schema/template/QC together or normalizes the 19 out-of-contract records back onto the documented enums.

### 4. The “latest QC report is still failing” claim is stale

- status: `stale_fixed`
- severity: `high`
- title: The repo no longer reflects the failed-QC state described in one review
- which_reviews_raised_it: `Opus`
- current_repo_evidence_paths:
  - `research/intake/normalized/qc/2026-04-01__qc_report.json`
  - `research/intake/inbox/system_runs/2026-03-31__dedup__pass_03.json`
  - `research/intake/normalized/manifests/corpus__deduped.json`
  - `tracking/collab/stage_02_synthesis/eval_inventory/outputs/eval_metadata_repair.md`
- adjudication: This is stale. The current `2026-04-01__qc_report.json` is `pass`, has zero failures, and explicitly describes a reconciled 288-record freeze. The current `2026-03-31__dedup__pass_03.json` also now contains 288 normalized records and includes the eight eval metadata repair backfills that Opus described as missing. The old fail-state narrative does not match the current repo.
- why_it_matters_now: This resolved disagreement matters because reopening a no-longer-live QC failure would waste the next cleanup slice.
- minimum_fix_or_operating_rule: Treat the current `2026-04-01` QC report and current `2026-03-31__dedup__pass_03.json` contents as ground truth; do not base new decisions on older review text that still references the failed 280-vs-288 state.

### 5. The blocked-exception layer is real, but “must demote all dead sources before synthesis” is overstated against the current synthesis partition

- status: `overstated`
- severity: `medium`
- title: The 41 blocked accepted records do not currently leak into the captured synthesis input
- which_reviews_raised_it: `Gemini`, `Opus`, `Codex`
- current_repo_evidence_paths:
  - `research/intake/rejected/2026-04-01__accepted_blocked_exceptions.json`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - `research/intake/normalized/manifests/corpus__deduped.json`
  - `research/intake/normalized/qc/2026-04-01__qc_report.json`
- adjudication: The underlying observation is true: 41 accepted records have no local artifact, and 36 of those blocked exceptions currently carry explicit `HTTP Error 404` block reasons. But the strongest review framing was too broad for the current frozen state. The blocked-exception set is disjoint from the 247 captured synthesis inputs, and the active capture manifest already excludes them cleanly. That means “demote every dead blocked exception before any deep synthesis can start” is not supported by current repo-state partitioning.
- why_it_matters_now: This is the main place where review language can create a false blocker. The project does need an explicit operating rule, but the current manifests do not show blocked exceptions leaking back into the active captured layer.
- minimum_fix_or_operating_rule: Treat `accepted_blocked_exceptions.json` as metadata-only exclusions for deep synthesis. Do not describe the project as having 288 openable sources, and do not cite blocked-exception records as if their artifacts exist locally.

### 6. `eval_inventory.md` is still stale relative to the repaired freeze

- status: `confirmed_but_nonblocking`
- severity: `medium`
- title: The eval inventory artifact still describes the pre-repair 280-record state
- which_reviews_raised_it: `Codex`
- current_repo_evidence_paths:
  - `tracking/collab/stage_02_synthesis/eval_inventory/outputs/eval_inventory.md`
  - `tracking/collab/stage_02_synthesis/eval_inventory/outputs/eval_metadata_repair.md`
  - `research/intake/normalized/manifests/evals_benchmarking__accepted.json`
  - `research/intake/normalized/manifests/corpus__deduped.json`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
- adjudication: This remains live but nonblocking. `eval_inventory.md` still says “280 intake records,” still says there are “31 relevant eval-oriented paper captures” without intake coverage, and still says “7 of the 29 accepted `evals_benchmarking` sources” lack `artifact_relpath`. `eval_metadata_repair.md` and the live manifests have already moved the freeze to 288 accepted records, 37 accepted eval IDs, and 247 captured sources.
- why_it_matters_now: The repo still contains a stale synthesis-prep artifact that can mislead downstream readers about what the April 1 repair slice actually fixed.
- minimum_fix_or_operating_rule: Mark `eval_inventory.md` as superseded for first-wave deep synthesis and use `eval_metadata_repair.md` plus the current manifests until the eval inventory is regenerated.

### 7. The current blocked-source snapshot is still stale by one record

- status: `confirmed_but_nonblocking`
- severity: `low`
- title: `current_blocked_accepted_sources.json` still misclassifies captured RALPH Loop as blocked
- which_reviews_raised_it: `Codex`, `Opus`
- current_repo_evidence_paths:
  - `research/intake/rejected/2026-04-01__current_blocked_accepted_sources.json`
  - `research/intake/rejected/2026-04-01__accepted_blocked_exceptions.json`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - `research/intake/records/src_cod_564b05dcc95b.json`
  - `research/sources/codebases/src_cod_564b05dcc95b/capture.json`
- adjudication: This remains live. `src_cod_564b05dcc95b` still appears in `current_blocked_accepted_sources.json`, but it is captured, present in `corpus__captured_for_synthetic_prep.json`, has a matching `capture.json`, and is not listed in `accepted_blocked_exceptions.json`.
- why_it_matters_now: It is a small but real contradiction in the prep layer, and it can confuse later cleanup passes if someone mistakes the stale snapshot for the authoritative blocked set.
- minimum_fix_or_operating_rule: Stop treating `current_blocked_accepted_sources.json` as authoritative. Use `accepted_blocked_exceptions.json` plus `corpus__captured_for_synthetic_prep.json` as the live partition.

### 8. The sparse eval backfills are a real synthesis-time caveat, not a prep blocker

- status: `confirmed_but_nonblocking`
- severity: `low`
- title: Some repaired eval records are intentionally shallow and should be treated as pointers to underlying artifacts
- which_reviews_raised_it: `Gemini`
- current_repo_evidence_paths:
  - `tracking/collab/stage_02_synthesis/eval_inventory/outputs/eval_metadata_repair.md`
  - `research/intake/records/src_pap_8c2cb08d2c57.json`
  - `research/intake/records/src_pap_97367f29ebbd.json`
  - `SYNTHESIS_TEAM_SPEC.md`
- adjudication: This remains directionally right but does not block deep synthesis on its own. The repair artifact explicitly says those two backfilled paper records were conservative and avoid unsupported abstract-level claims. The records are present, captured, and legitimate, but they are not rich standalone summaries.
- why_it_matters_now: A synthesis agent that reads only the intake metadata could underuse them or over-infer from titles. A synthesis agent that reads the underlying artifact paths is fine.
- minimum_fix_or_operating_rule: Treat these repaired eval records as index entries. When a backfilled record explicitly says it was conservative, read the underlying paper capture before making mechanism-level claims.

## Consensus Findings

- `Codex` and `Opus` were both right that six placeholder/mock records still survive in the accepted corpus.
- `Codex`, `Gemini`, and `Opus` all correctly identified the need to distinguish the 288 accepted records from the smaller set of directly openable synthesis inputs.
- `Codex` and `Opus` were both right that `current_blocked_accepted_sources.json` is stale relative to the live captured/blocked partition.
- `Codex` and `Opus` were both directionally right that the frozen intake layer is not the full synthesis-ready evidence inventory.

## Disagreements Between Reviews

- QC state:
  - `Opus` said the latest QC report was still `fail`.
  - Current repo state shows `research/intake/normalized/qc/2026-04-01__qc_report.json` is `pass`, and the current `2026-03-31__dedup__pass_03.json` already contains the repaired 288-record state.
- Schema cleanliness:
  - `Codex` said schema/enum drift was live.
  - `Opus` said no schema regressions remained.
  - Current repo evidence supports Codex on enum drift against the documented shared schema/template, with the caveat that normalized records are also separately documented to add extra fields.
- Whether blocked accepted exceptions must be demoted before synthesis:
  - `Gemini` treated dead blocked exceptions as must-demote items.
  - Current repo partitioning shows they are already excluded from the captured synthesis manifest, so blanket pre-synthesis demotion is not required if scope is explicit.
- Whether the project is safe to proceed:
  - `Gemini` judged the repo conditionally safe.
  - `Codex` and `Opus` judged it unsafe.
  - Current repo evidence supports a narrower version of the `Codex` and `Opus` position: the blocker is unresolved synthesis-prep scope/routing, not failed QC arithmetic.

## New Findings Not Raised By All Three

- No additional high-severity defect missed by all three reviews was confirmed in the current repo state.
- The strongest correction is numerical, not directional: the omitted repo-local capture count is still materially nonzero, but the current repo-local comparison shows `75` unindexed captured paper/doc source dirs rather than the `82` cited in earlier review text.
- The current repo state also makes one governance point sharper than the earlier reviews did: the missing evidence-inventory organizer is now the clearest single blocker because it is the artifact that should have resolved the competing scope stories.

## Findings Invalidated By The Passing QC

- The claim that the latest QC report is still failing is invalidated by `research/intake/normalized/qc/2026-04-01__qc_report.json`.
- Any claim that the current dedup pass still only contains 280 normalized records is invalidated by the present contents of `research/intake/inbox/system_runs/2026-03-31__dedup__pass_03.json`.
- Any claim that blocked exceptions currently leak into the captured synthesis manifest is invalidated by the current captured/blocked partition in the manifests and QC warning text.

## Must Fix Before Deep Synthesis

- Write the missing Stage 2A evidence organizer or issue an equivalent principal scope note that explicitly defines the first-wave deep-synthesis evidence boundary.
- Make the active synthesis input unambiguous: first-wave deep synthesis must use `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`, not the broader 288-record accepted manifest.
- Mark `tracking/collab/stage_02_synthesis/eval_inventory/outputs/eval_inventory.md` and `research/intake/rejected/2026-04-01__current_blocked_accepted_sources.json` as superseded/non-authoritative for first-wave synthesis routing.

## Safe To Proceed Judgment

Not yet safe to proceed into unconstrained deep synthesis.

The repo is no longer blocked by failed QC arithmetic, demotion leakage, or blocked-exception leakage into the captured manifest. The remaining blockers are narrower but still material: Stage 2A has not yet written the scope-closing evidence organizer, stale prep artifacts still contradict the repaired freeze, and the accepted corpus still contains six obviously false-provenance records that will remain dangerous unless deep synthesis is explicitly routed only through the 247 captured-source manifest.

If the project first closes scope in writing and treats the 41 blocked exceptions, including the six placeholder/mock records, as out-of-scope metadata-only exclusions, then deep synthesis can begin against the captured freeze without reopening QC, dedup, or capture.

## Recommended Next Hand Off Target

Principal project steward, for one narrow synthesis-prep cleanup/governance slice that:

- writes `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` or an equivalent authoritative scope note,
- marks stale prep artifacts as superseded for first-wave synthesis routing,
- and instructs the deep-synthesis lane to operate only on the 247 captured source IDs while treating blocked exceptions as non-evidence metadata.
