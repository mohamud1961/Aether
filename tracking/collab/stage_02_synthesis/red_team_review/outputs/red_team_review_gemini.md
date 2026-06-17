# RED_TEAM_REVIEW_OUTPUT

## Findings

### 1. QC Pipeline operates blindly without empirical repo access
- **Severity**: high
- **Repo Evidence Paths**: `research/source_finder_prompt_pack/prompts/quality_control.md`, `research/intake/normalized/qc/2026-04-01__qc_report.json`
- **Direct Observation**: The QC agent explicitly states: "You have no repo access unless the operator pastes the needed data". It enforces claim structure and provenance fields entirely on normalized JSON records and inbox batch files.
- **Why it matters**: The QC pass can only validate structural JSON schemas and the formatting of `claim_locations`. It cannot empirically verify that the mechanistic detail extracted actually exists in the local PDF or markdown artifacts. The pipeline claims "QC blind spots or false-confidence failure modes" are resolved, but QC is entirely decoupled from the source evidence. Hallucinated claims by the source-finder would pass QC as long as they are formatted correctly.
- **Minimum fix**: Grant the QC agent limited repo access to `research/sources/` or run a secondary sampling pass that cross-references `claim_locations` against the raw artifact text.

### 2. Backfilled eval records lack substantive metadata, risking synthesis hallucination
- **Severity**: high
- **Repo Evidence Paths**: `tracking/collab/stage_02_synthesis/eval_inventory/outputs/eval_metadata_repair.md`, `research/intake/records/src_pap_8c2cb08d2c57.json`, `research/intake/records/src_pap_97367f29ebbd.json`
- **Direct Observation**: The metadata repair explicitly states that backfilled papers without abstracts (e.g., DeepPlanning, AgentLongBench) intentionally avoid unsupported abstract-level claims. The resulting records have `claim_snippets` that just confirm the benchmark name and URL link.
- **Why it matters**: The synthesis-prep pipeline normally relies on `claim_snippets` for deep synthesis. If the synthesis agent reads these backfilled records alone, it will find no mechanistic claims and may either discard the source as low-signal or hallucinate mechanisms based on the title. The current pipeline design assumes records contain 1-5 concrete claims, but these backfills safely but silently bypass that contract.
- **Minimum fix**: Add explicit instructions to the Stage 2 Synthesis team spec mandating that for backfilled or sparse records, the agent must read the underlying `artifact_relpath` PDF rather than relying solely on the intake record metadata.

### 3. Known dead sources are retained as accepted blocked exceptions
- **Severity**: medium
- **Repo Evidence Paths**: `research/intake/rejected/2026-04-01__accepted_blocked_exceptions.json`, `research/intake/records/src_cod_1329f0fbee94.json`, `research/intake/records/src_cod_fdebc7a1cec5.json`
- **Direct Observation**: Sources like `src_cod_1329f0fbee94` (`oracle-failover-trace`) and `src_cod_fdebc7a1cec5` (`lobehub/agent-harness/protocols`) are marked as 404s and remain in the accepted blocked exceptions list.
- **Why it matters**: These are not transient network errors; they are dead repos with no successors. Retaining them as accepted exceptions inflates the corpus value and leaves the synthesis agent expecting to find valid evidence that no longer exists on the internet or locally. They should be manually demoted.
- **Minimum fix**: Move confirmed 404 dead repos from `accepted_blocked_exceptions.json` into `manual_demotions.json` and adjust the total `accepted_source_count` accordingly.

### 4. Untidy artifact extraction leaking to workspace root
- **Severity**: low
- **Repo Evidence Paths**: `./make-mips-interpreter__F67iyDa/`, `./3aeb3377-4225-46c6-93ea-6184690b68d1-traj.txt`
- **Direct Observation**: Several trajectory task folders and `.txt` files exist directly in the workspace root.
- **Why it matters**: While this doesn't materially contradict the eval inventory conclusions (which correctly found the 89 folders in BigAI, deepagents, and terminus-kira), it shows sloppy artifact handling or a broken test script. It risks muddying grep searches and context during synthesis.
- **Minimum fix**: Delete these leaked trajectory assets from the workspace root.

## Confirmed Strengths
- **Manifest Counts Perfectly Reconcile**: The numbers match the contract explicitly. There are 247 captured sources and 41 accepted blocked exceptions, totaling 288 accepted sources. All 288 accepted source IDs map to an existing, valid `.json` record in `research/intake/records/`.
- **No Demotion Leakage**: No quarantined duplicate IDs (5 items) or manually demoted IDs (16 items) leaked back into the active `corpus__captured_for_synthetic_prep.json` or `corpus__deduped.json`.
- **Artifact Presence**: All 247 captured source IDs in the synthetic prep manifest successfully map to an existing local `artifact_relpath` directory.
- **Trajectory Inventory Integrity**: The trajectory corpus counts (`BigAI`, `deepagents`, and `terminus-kira` each covering 89 shared task folders) are accurate and fully present in the local `research/sources/trajectories/` paths.

## Residual Risks if Proceeding Now
- The synthesis agent may ignore backfilled papers because their metadata records are shallow, unless explicitly told to dive into the raw PDFs.
- The synthesis agent may attempt to summarize dead sources (like `oracle-failover-trace`) based entirely on their titles because the source has no local artifact.

## Must Fix Before Deep Synthesis
- Update the Synthesis agent prompt/instructions to explicitly handle sparse backfilled records by deeply reading the raw `artifact_relpath` files rather than trusting metadata alone.
- Manually demote the definitively dead 404 sources from the accepted blocked exceptions list.

## Safe to Proceed Judgment
Yes, conditionally safe to proceed. The pipeline is structurally sound, and artifact counts are highly accurate. The risks are primarily around synthesis agent behavior when encountering sparse or dead records rather than a fundamental break in corpus integrity. Provided the deep synthesis prompt accounts for these edge cases, it is safe to proceed.

## Recommended Next Hand-Off Target
Hand off to the Principal Project Steward to apply the minimal demotion fixes and update the `SYNTHESIS_TEAM_SPEC.md` before kicking off the first wave of Deep Synthesis.