RED_TEAM_REVIEW_OUTPUT

## Findings

### 1. Placeholder and mock source identities survived all the way into the frozen accepted corpus
- severity: critical
- title: Known-noncanonical placeholder locators are still accepted inputs
- repo evidence paths:
  - `research/intake/records/src_pap_1a2b3c4d5e6f.json`
  - `research/intake/records/src_pap_5e6f1a2b3c4d.json`
  - `research/intake/records/src_pap_b2c3d4e5f6a1.json`
  - `research/intake/records/src_pap_d4e5f6a1b2c3.json`
  - `research/intake/records/src_pap_e5f6a1b2c3d4.json`
  - `research/intake/records/src_trc_1a3b5c7d9e2f.json`
  - `research/intake/rejected/2026-04-01__accepted_blocked_exceptions.json`
  - `research/intake/inbox/supplemental_runs/2026-03-29__tool_calling_methodologies_sweep.json`
  - `research/intake/inbox/supplemental_runs/2026-03-29__workflow_control_policy_sweep.json`
  - `research/intake/inbox/system_runs/2026-03-31__dedup__pass_03.json`
  - `research/source_finder_prompt_pack/prompts/canonical_source_finder_template.md`
  - `research/source_finder_prompt_pack/prompts/quality_control.md`
- direct observation: Six accepted records still use obviously placeholder locators such as `https://arxiv.org/abs/infoqa_mock`, `https://arxiv.org/abs/trm_mock`, `https://arxiv.org/abs/simpletool_mock`, `https://arxiv.org/abs/gap_benchmark_mock`, `https://arxiv.org/abs/reponavigator_mock`, and `https://traces.example.org/analysis/stop-policy-failure`. All six remain in `corpus__deduped.json` via their record files, all six sit in `accepted_blocked_exceptions.json`, the same placeholder values appear in the raw supplemental intake files, and neither the base source-finder template nor the QC prompt contains an explicit reject-placeholder rule.
- why it matters: This is not just sparse coverage; it is false provenance inside the accepted corpus. A downstream synthesis pass that treats accepted records as trustworthy can cite or reason over sources that were never canonical, never openable, and may never have existed.
- minimum fix: Remove or replace all six placeholder IDs before deep synthesis. Then add an explicit source-finder and QC gate that rejects `_mock`, `example.com`, `example.org`, and other placeholder locators instead of merely letting capture fail later.

### 2. The documented intake contract is not the contract the accepted records actually satisfy
- severity: high
- title: Schema and enum drift is live in accepted records, but QC still reports a clean pass
- repo evidence paths:
  - `research/source_finder_prompt_pack/shared_json_schema.json`
  - `research/source_finder_prompt_pack/prompts/canonical_source_finder_template.md`
  - `research/source_finder_prompt_pack/prompts/quality_control.md`
  - `research/intake/normalized/qc/2026-04-01__qc_report.json`
  - `research/intake/rejected/2026-04-01__qc__blocked.json`
  - `research/intake/inbox/bucket_runs/2026-03-25__execution_control.json`
  - `research/intake/inbox/bucket_runs/2026-03-25__tooling_tool_gateway.json`
  - `research/intake/records/src_doc_86dfad9d959c.json`
  - `research/intake/records/src_doc_ded84a79b0f5.json`
  - `research/intake/records/src_iss_89b2c3d4e5f1.json`
  - `research/intake/records/src_pap_163afe88846b.json`
- direct observation: The shared schema and source-finder template still define closed enums for fields like `artifact_type`, `decision_targets`, `task_regime`, and `environment_type`, but a repo-local comparison against the 288 accepted records finds 19 records that violate those enums. Concrete examples include `artifact_type: "SEP"`, `"blog_post"`, `"discussion"`, and `"preprint"`; `decision_targets` like `step_verification`, `human_in_the_loop`, `termination`, and `formal_verification`; `task_regime` values like `long_running_task` and `software_engineering_agent`; and `environment_type` values like `any`, `sandbox_container`, and `formal_simulator`. Some of those off-schema values already appear in raw bucket intake, yet `2026-04-01__qc_report.json` still says `status: "pass"` and `2026-04-01__qc__blocked.json` is empty.
- why it matters: The project cannot claim both “same interfaces” and “schema-clean accepted records” while keeping a silent parallel vocabulary. Any downstream automation, filtering, or synthesis prompt built against the documented contract is now brittle by default, and the QC pass is overstating what it really validated.
- minimum fix: Pick one contract and enforce it. Either ratify the expanded vocabulary by updating schema, prompts, and QC together, or normalize the 19 affected records back onto the documented enums and rerun QC against that real contract.

### 3. The “frozen corpus” still excludes mandatory evidence classes and 82 captured sources that never entered intake governance
- severity: high
- title: Deep synthesis would still miss major repo-local evidence if it trusts the intake layer alone
- repo evidence paths:
  - `tracking/collab/stage_02_synthesis/README.md`
  - `tracking/collab/stage_02_synthesis/evidence_inventory/brief.md`
  - `tracking/collab/stage_02_synthesis/evidence_inventory/decision.md`
  - `tracking/collab/stage_02_synthesis/eval_inventory/outputs/eval_inventory.md`
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/README.md`
  - `research/intake/records/`
  - `research/intake/normalized/manifests/corpus__deduped.json`
  - `research/intake/rejected/2026-04-01__accepted_blocked_exceptions.json`
  - `research/sources/informal/`
  - `research/sources/trajectories/`
  - `research/sources/papers/src_pap_41411a54915e/capture.json`
  - `research/sources/papers/src_pap_8f63b3982250/capture.json`
  - `research/sources/papers/src_pap_848e64807b43/capture.json`
  - `research/sources/papers/src_pap_745ff5b9489c/capture.json`
  - `research/sources/papers/src_pap_703731e7c236/capture.json`
  - `research/sources/papers/src_pap_1aa5f045a3b6/capture.json`
- direct observation: Stage 02 guidance says trajectories are a top-priority evidence class and informal sources must stay in scope, while the eval inventory calls the three trajectory corpora the strongest local behavioral evidence and notes 102 informal markdown captures. But the current accepted record set has zero `artifact_relpath` entries under `research/sources/trajectories/` and zero under `research/sources/informal/`. A repo-local enumeration of `research/sources/**/src_*` against the accepted and rejected manifests also finds 82 captured `src_*` directories that are not represented in any active or rejected intake manifest. Sample omitted captures include `SoK: Agentic Skills - Beyond Tool Use in LLM Agents`, `MCP Security Bench (MSB)`, `FinToolBench`, `AgentAssay`, `AMA-Bench`, and `AgentSpawn`. On top of that, `tracking/collab/stage_02_synthesis/evidence_inventory/decision.md` says the first synthesis-prep artifact must be `outputs/organizer.md`, but the `outputs/` folder still only contains `README.md`.
- why it matters: The project is about to trust a frozen intake/manifests layer that is not actually coterminous with the strongest local evidence. That makes the corpus both incomplete and scope-ambiguous: a synthesis agent can either miss mandatory evidence classes or quietly improvise a second evidence intake path with no governance.
- minimum fix: Before deep synthesis, either produce the missing evidence-inventory organizer and explicit routing rules for trajectories, informal evidence, and the 82 unindexed captures, or formally narrow the claimed synthesis scope so the 288-record intake layer is no longer treated as the full synthesis-prep corpus.

### 4. The eval inventory artifact is already stale relative to the repaired frozen state
- severity: medium
- title: Eval-prep documentation still describes the pre-repair corpus
- repo evidence paths:
  - `tracking/collab/stage_02_synthesis/eval_inventory/outputs/eval_inventory.md`
  - `tracking/collab/stage_02_synthesis/eval_inventory/outputs/eval_metadata_repair.md`
  - `research/intake/normalized/manifests/evals_benchmarking__accepted.json`
  - `research/intake/normalized/manifests/corpus__deduped.json`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
- direct observation: `eval_inventory.md` still states “280 intake records,” says there are “31 relevant eval-oriented paper captures” without intake coverage, and says “7 of the 29 accepted `evals_benchmarking` sources” lack `artifact_relpath`. The repair artifact and current manifests have already moved the frozen state to 288 accepted records, 37 accepted eval IDs, and 247 captured sources.
- why it matters: This is a repo-local contradiction inside the synthesis-prep layer itself. Any downstream reviewer or synthesis pass using both the inventory artifact and the live manifests will receive conflicting instructions about what is already fixed versus still missing.
- minimum fix: Regenerate `eval_inventory.md` from the repaired freeze state or mark it explicitly superseded so synthesis consumers only see one current eval inventory.

### 5. A stale blocked-source snapshot still contradicts the frozen capture state
- severity: low
- title: `current_blocked_accepted_sources.json` still marks RALPH Loop as blocked after capture succeeded
- repo evidence paths:
  - `research/intake/rejected/2026-04-01__current_blocked_accepted_sources.json`
  - `research/intake/rejected/2026-04-01__accepted_blocked_exceptions.json`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - `research/intake/records/src_cod_564b05dcc95b.json`
  - `research/sources/codebases/src_cod_564b05dcc95b/capture.json`
- direct observation: `src_cod_564b05dcc95b` appears in `current_blocked_accepted_sources.json`, but it is present in the captured synthetic-prep manifest, has a matching accepted record and `capture.json`, and does not appear in `accepted_blocked_exceptions.json`.
- why it matters: This file is no longer authoritative, but it still lives in the same rejection area as active blocked-source artifacts. Future cleanup or review passes can read it as current truth and misclassify one captured source as still blocked.
- minimum fix: Regenerate or retire `current_blocked_accepted_sources.json`, and point future consumers at `accepted_blocked_exceptions.json` plus `corpus__captured_for_synthetic_prep.json` as the only live blocked/captured partition.

## Confirmed Strengths

- The core manifest arithmetic is coherent. `corpus__deduped.json`, `corpus__captured_for_synthetic_prep.json`, `accepted_blocked_exceptions.json`, and `research/intake/records/` reconcile cleanly at 288 accepted, 247 captured, and 41 explicit blocked exceptions.
- I found no leakage of manually demoted IDs from `research/intake/rejected/2026-04-01__manual_demotions.json` and no leakage of the Terminal-Bench duplicate quarantine ID from `research/intake/rejected/2026-04-01__synthesis_duplicate_quarantine.json` back into the active synthesis inputs.
- I found no confirmed capture-to-record mismatch in the 247 captured IDs. The sampled backfilled eval records and their capture wrappers were conservative and capture-aligned rather than obviously over-inferred.

## Residual Risks If Proceeding Now

- Even after removing the six placeholder records, the accepted corpus would still contain 41 blocked exceptions, and 36 of those currently carry explicit `HTTP Error 404` block reasons. The project should not talk about “288 openable sources.”
- Until the evidence-inventory organizer exists, any deep synthesis run will need ad hoc human routing to know when it must read trajectories, informal captures, or unindexed `research/sources/*` evidence directly.
- Until the schema contract is reconciled, downstream tooling that groups or filters by enum values will remain vulnerable to silent dropouts or inconsistent aggregation.

## Must Fix Before Deep Synthesis

- Remove or replace the six placeholder/mock accepted records and rerun the frozen QC pass.
- Reconcile the accepted-record schema contract with the actual vocabulary in use, then rerun QC against that real contract.
- Decide whether Stage 2A synthesis will operate on the full repo-local evidence base or only on the 288-record intake layer, and encode that decision in the missing evidence-inventory organizer.
- Refresh or supersede `tracking/collab/stage_02_synthesis/eval_inventory/outputs/eval_inventory.md` so synthesis consumers do not inherit stale pre-repair counts.

## Safe To Proceed Judgment

Not safe to proceed into deep synthesis yet.

The current freeze is internally partitioned, but it is not yet trustworthy enough as a synthesis boundary. The critical blocker is false provenance inside accepted records. The next blockers are contract drift that QC is not actually catching and a still-unresolved mismatch between the “frozen corpus” story and the stronger repo-local evidence that Stage 02 says should guide synthesis.

## Recommended Next Hand Off Target

Principal project steward, routing a repo-access synthesis-prep cleanup slice that handles placeholder-source demotion, contract/QC reconciliation, and evidence-scope closure before any deep synthesis artifact opens.
