# Wave 05 Contradiction Analyst Output (External: Claude Gate Review)

```text
DEEP_SYNTHESIS_CONTRADICTION_OUTPUT
- artifact: mechanism_map
- wave: wave_05_tools_environment_permissions
- reviewer_type: external_claude_gate
- overall_verdict: pass_with_warnings
- preflight_scope_confirmed:
  - confirmed this contradiction pass is scoped to Wave 05 tools/environment/permissions, not generic execution-control or state-memory synthesis.
  - confirmed packet default keeps eval fifth lane inactive; eval-side reasoning appears only as non-binding carry-forward pressure in the literature lane.
  - confirmed trajectory/failure is the primary empirical anchor for this wave.
  - critical context change: the primary GPT and Gemini contradiction reviews returned `blocked` because `trajectory_failure_analyst.md` was missing. That file now exists (286 lines, 23KB) with two support artifacts (`trajectory_support_tool_environment_matrix.md`, `trajectory_support_permission_boundary_cases.md`). The structural blocker that motivated the prior `blocked` verdict is resolved.
  - the four required first-pass lane outputs are present and substantive:
    - trajectory_failure_analyst.md (286 lines)
    - codebase_source_reconstruction_analyst.md (315 lines)
    - literature_papers_docs_analyst.md (197 lines)
    - informal_issues_postmortems_analyst.md (191 lines)
  - four support artifacts are present:
    - trajectory_support_tool_environment_matrix.md
    - trajectory_support_permission_boundary_cases.md
    - codebase_support_tool_gateway_map.md
    - codebase_support_environment_permission_map.md
  - three dossier-level support artifacts are present:
    - tracking/collab/stage_02_synthesis/literature_dossiers/themes/tool_use_and_gateways.md
    - tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md
    - tracking/collab/stage_02_synthesis/informal_cluster_dossiers/tools_environment_permissions.md
- preflight_planned_read_order:
  - 1. wave control surfaces and carry-forward constraints:
    - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/brief.md
    - tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md
    - tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md
    - tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md
    - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md
    - tracking/collab/stage_02_synthesis/coverage_register/current_status.md
  - 2. all four Wave 05 first-pass lane outputs
  - 3. all four Wave 05 support artifacts
  - 4. three Wave 05 dossier-level support artifacts
  - 5. contradiction analyst prompt and wave contradiction packet
  - 6. prior GPT and Gemini contradiction outputs for context on resolved blockers
- preflight_critical_sources_selected:
  - control and carry-forward surfaces:
    - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/brief.md
    - tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md
    - tracking/collab/stage_02_synthesis/coverage_register/current_status.md
  - all four first-pass lane outputs (now present)
  - all four support artifacts (now present)
  - trajectory evidence paths cited by trajectory lane
  - source evidence paths cited by codebase lane
  - issue/informal evidence paths cited by informal lane
  - formal docs and papers evidence paths cited by literature lane
- preflight_coverage_risks:
  - coverage register still shows Wave 05 as "packet prepared, not started" despite all four lanes now having outputs; governance surface is stale.
  - deepagents extract-moves-from-video trajectory is cancel-only (immediate `CancelledError`), reducing empirical tool/environment exercise for that family in that task regime.
  - required case-study path `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md` is still absent (noted by both codebase and trajectory lanes).
  - organizer control surface remains empty: `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`.
  - BigAI remains no-source; all BigAI claims are bound to behavioral reconstruction.
- preflight_likely_blind_spots:
  - eval/benchmark lane is inactive; benchmark-side tool or environment contracts are untested.
  - browser-substrate trajectory evidence is thin in the required Wave 05 slices; only KIRA extract-moves shows multimodal hybridization (`image_read`).
  - long-tail `git-multibranch` trajectory pressure for cwd/worktree boundaries is optional and was not included.
  - hidden runtime approval-policy internals not logged in trajectory text remain invisible.
- preflight_blockers:
  - none structural. The prior structural blocker (missing trajectory lane) is resolved.
  - governance/register stale-state: coverage register needs updating but this is a maintenance issue, not a synthesis blocker.
  - missing `headless_terminal.md` case study: this weakens support-track completeness but is explicitly listed in the brief as deferrable without blocking contradiction review.
```

## Attack Surface Analysis

### 1. Fake tool-gateway sophistication without source or behavior support

Verdict: defended.

Observation: The trajectory lane (W05-T1) identifies three materially different tool gateway surfaces and anchors each in specific trajectory evidence. The codebase lane independently confirms these with source-backed claims: deepagents middleware/backend split, KIRA engine-managed tool composition with MCP runtime, a-evolve two-tier minimal-terminal plus dynamic-MCP gateway. The support artifact `codebase_support_tool_gateway_map.md` provides a tabular cross-family comparison with per-cell citations.

Adversarial pressure applied: I checked whether any lane claims a richer gateway architecture than the evidence supports. The literature lane (Claim 2, Claim 3) describes formal deferred-discovery and code-mediated orchestration doctrine from OpenAI/Anthropic docs, but explicitly self-caveats that "formal material is richer on policy and architecture doctrine than direct trajectory proof." The trajectory lane independently confirms the minimal-sufficient baseline (W05-T5): "browser-first prestige is not supported by this wave's required trajectories; the strongest completions are terminal-centric." The codebase lane correctly classifies a-evolve MCP as dynamic expansion on top of a minimal terminal baseline, not as default sophistication.

Remaining tension: the trajectory lane notes BigAI shows the richest explicit process-orchestration gateway (`run`/`wait`/`kill`/`interact`) but this is behavioral reconstruction only, and all four lanes maintain this caveat. No lane silently upgrades BigAI beyond reconstruction.

Confidence: high that this attack surface is clean.

### 2. Fake sandbox or permission safety claims

Verdict: defended with carry-forward warning.

Observation: No lane claims robust permission safety is established. The trajectory lane (W05-T4) explicitly states: "this lane can promote permission-friction candidates, but not strong claims of robust permission safety." The codebase lane identifies KIRA's heterogeneous permission doctrine (allow/deny/ask in KiraClaw vs `bypassPermissions` in KIRA-Slack) as a real source-backed finding, not a safety claim. The informal lane independently identifies the bifurcated failure mode (under-enforcement AND over-prompting) with converging issue evidence across 7 issue reports.

Adversarial pressure applied: I checked whether any lane treats container isolation or sandbox configuration as equivalent to permission safety. The codebase lane correctly separates these: deepagents local-shell backend "explicitly warns there is no sandboxing" (claim_02); a-evolve relies on Docker container lifecycle but has "limited explicit allow/deny guard in terminal tool path" (codebase claim_06, codebase_support_tool_gateway_map). No lane conflates containerization with approval doctrine.

Remaining tension: the formal literature lane (Claim 5) cites OAP as showing "formal mechanism separation between authorization and sandboxing is mature enough to treat as distinct Wave 05 subfamilies." This is a formal-source claim, and the literature lane correctly notes it does not override stronger behavior/source evidence. However, the gap between this formal maturity claim and the trajectory evidence (which shows no end-to-end approval-policy protocol in any required slice) is a real tension that should be carried forward.

Carry-forward warning: permission safety remains under-evidenced at the trajectory level. Formal and source evidence show substrate capacity for approval/sandbox separation, but required trajectories do not demonstrate enforcement. This mismatch must remain visible in principal synthesis.

Confidence: high on the safety-claim defense; medium on the trajectory gap.

### 3. Hidden environment assumptions that are not validated in-run

Verdict: defended with nuance.

Observation: The trajectory lane (W05-T2) identifies environment discovery as a recurring precondition mechanism at medium confidence, correctly noting that "BigAI evidence is behavioral reconstruction; KIRA evidence in this lane is prompt-shape heavy." The codebase lane provides source-backed evidence: deepagents local-context middleware runs a detection script and injects results; a-evolve has a seed environment-discovery skill; KIRA centralizes workspace/MCP/browser settings. The informal lane adds pressure on localhost hook failures (ECONNREFUSED issue) where "environment discovery and precondition checks must include local-hook reliability."

Adversarial pressure applied: I tested whether environment discovery claims are inflated beyond what trajectories actually show. The trajectory support matrix confirms: only DeepAgents headless-terminal shows explicit startup `environment_context`. Other families show implicit or absent discovery signals. The trajectory lane's medium confidence is appropriate given this thinness.

Remaining tension: the gap between source-visible environment-discovery capacity (deepagents local_context, a-evolve SKILL.md) and trajectory-visible exercise of that capacity remains open. This is a real source/behavior mismatch that should be carried forward.

Confidence: medium. Claims are honest but the trajectory-side anchor is thin for environment discovery outside DeepAgents headless-terminal.

### 4. CWD/workdir/path/process-discipline overclaims

Verdict: defended.

Observation: The trajectory lane (W05-T3) identifies cwd/workdir discipline as a "first-order failure boundary" at high confidence, anchored in a specific BigAI cancel-async failure (`No module named 'run'` under `/tmp`). The codebase lane provides converging source evidence: deepagents `validate_path` blocks traversal, KIRA process manager rejects invalid/non-dir resolved paths, a-evolve terminal prompt states each bash call is independent. The informal lane adds cross-platform pressure: wrong-file-loop/path-contamination, relative-vs-absolute permission mismatch, UNC/mapped worktree failures.

Adversarial pressure applied: I tested whether the promoted confidence exceeds the spread of evidence. The trajectory-level anchor is strongest from one BigAI run family and one KIRA extract-moves slice. Source evidence is broader (three families). The trajectory lane self-caveats: "strongest direct example is from one BigAI run family." The informal lane broadens the evidence base with Windows/UNC specifics that trajectory evidence does not cover but that are outside the required trajectory scope.

Remaining tension: cwd/workdir discipline claims are well-supported as a mechanism family, but the cross-family behavioral saturation is still concentrated in `cancel-async-tasks` for direct trajectory proof. The trajectory lane's self-caveat is honest and should be preserved.

Confidence: high. No overclaim detected; caveats are in place.

### 5. Browser/tool prestige overclaims

Verdict: defended.

Observation: The trajectory lane (W05-T5) explicitly blocks browser-prestige promotion: "baseline mechanism remains shell-plus-file tooling with disciplined cwd/process handling; richer substrate is conditional, not default superiority." Only KIRA's `image_read` in extract-moves-from-video shows selective multimodal uplift. The literature lane preserves Wave 04 carry-forward: "richer formal gateway/sandbox stacks must not silently displace that baseline without trajectory/source reconciliation." The informal lane separates browser capability from browser reliability: "browser-crash non-recovery reports indicate the browser substrate is still a failure-prone runtime surface."

Adversarial pressure applied: I searched for any lane that treats browser integration as a reliability advantage rather than a capability expansion. Found none. The a-evolve codebase findings (two-tier gateway) explicitly maintain the minimal terminal baseline as the first tier.

Confidence: high that this attack surface is clean. Minimal-sufficient baseline is preserved across all lanes.

### 6. Source/trajectory mismatches on tool or permission behavior

Verdict: mismatches are present, honestly reported, and should be carried forward.

Observation: The codebase lane explicitly documents three source/behavior mismatches:
  - mismatch_01: deepagents source supports richer environment/MCP than required trajectories exercise (extract-moves slice is cancel-only).
  - mismatch_02: KIRA source advertises structured tool routing, but extract trajectory shows repeated command-format errors.
  - mismatch_03: local harness code is interface-only stubs, so no reconciliation is possible.

The trajectory lane's tool-environment matrix confirms the thin exercise of deepagents tool substrate in extract-moves (no sustained tool sequence due to early abort). KIRA's headless-terminal and cancel-async trajectories show stable tool exercise, but extract-moves shows environmental friction (cv2 missing, venv churn).

Adversarial pressure applied: I specifically tested whether any promoted claim depends on source capacity that is not exercised in required trajectories. The codebase lane's promoted claims for deepagents (claim_01 through claim_03) are anchored in headless-terminal and cancel-async trajectories where tool exercise is real. The cancel-only extract-moves slice weakens family completeness but does not undermine the promoted claims because those claims cite the other two tasks.

KIRA claim_05 (heterogeneous permission doctrine) is entirely source-backed across two subprojects and does not claim trajectory-level confirmation, correctly marking itself at medium confidence. This is honest.

Carry-forward warning: the deepagents extract-moves cancel-only trajectory and the KIRA extract-moves command-format noise represent a real trajectory-side weakness for those families in that task regime. They should remain visible.

Confidence: high that mismatches are honestly reported. Medium that this thin slice does not hide a deeper problem.

### 7. Silent eval-lane reasoning while eval is inactive

Verdict: clean with minor caution.

Observation: The literature lane includes benchmark-definition notes (MCPAgentBench, Try-Check-Retry) and eval-relevance framing. This was flagged by the primary GPT contradiction review as acceptable "non-binding pressure" and I concur. The literature lane explicitly classifies this as benchmark-definition sharpening, not active eval adjudication. No other lane performs eval reasoning.

Caution: the literature lane's explicit mechanism support families include "typed tool-schema gateway" and "deferred tool discovery and load control," which could bleed into eval-implications territory. These are currently framed as formal-source mechanism pressure, not eval policy, and should stay that way.

Confidence: high that eval boundary is respected.

### 8. Support artifacts used as promoted claims

Verdict: clean.

Observation: All four support artifacts explicitly state they "do not promote mechanism conclusions by themselves" or equivalent language. The trajectory support matrix and permission boundary cases are inventories and case tables, not synthesis. The codebase support maps are structured evidence summaries with explicit confidence postures. Main-lane analysts synthesize and cite these artifacts without delegating their analytical responsibilities.

Confidence: high.

### 9. BigAI treated beyond behavioral reconstruction

Verdict: clean.

Observation: All four lanes maintain the behavioral-reconstruction boundary for BigAI. The trajectory lane labels every BigAI run entry as "(behavioral reconstruction context)." The codebase lane's reconstruction_01 and reconstruction_02 are explicitly labeled and carry medium-to-low confidence. The codebase support gateway map row for BigAI says "must remain behavioral reconstruction." The informal lane carries forward: "BigAI remains behavioral reconstruction and should not be upgraded by informal analogy."

Adversarial pressure applied: I checked whether the trajectory lane's process-orchestration finding (W05-T1 noting BigAI's `run`/`wait`/`kill`/`interact` gateway) could be over-read as source-backed implementation design. The trajectory lane says "BigAI mechanism internals are not source-visible in this lane" and the codebase lane's reconstruction notes carry explicit "no mirrored source; mechanism internals remain hidden" caveats.

Confidence: high that BigAI boundary is maintained.

## Cross-Lane Reconciliation Assessment

### Trajectory-to-Source reconciliation

Status: materially achieved for the required domain.

The trajectory lane identifies three distinct tool gateway families behaviorally. The codebase lane confirms these with source-backed implementation evidence for deepagents, KIRA, and a-evolve. Key reconciliation points:
  - DeepAgents trajectory tool surface (`execute`, `write_file`, `edit_file`, `read_file`, `grep`) matches source-visible middleware tool stack (codebase match_02, high confidence).
  - KIRA trajectory tool surface (`bash_command`, `image_read`, `mark_task_complete`) matches source-visible native tool architecture (codebase match_01, high confidence).
  - BigAI trajectory tool surface (`run_shell_command`, `wait_shell_command`, `kill_shell_command`, `interact_with_shell`) is behavioral-reconstruction only; no source reconciliation possible.
  - CWD/workdir failure (BigAI `/tmp` pathing) aligns with deepagents source-backed `validate_path` and KIRA source-backed cwd validation as convergent mechanism evidence for path discipline.

Remaining reconciliation gap: deepagents MCP trust gating and KIRA MCP runtime startup controls are source-visible but not trajectory-exercised in required slices.

### Trajectory-to-Informal reconciliation

Status: materially achieved with explicit limits.

The trajectory lane's permission-friction candidates (W05-T4, medium confidence) align with the informal lane's high-signal finding that "permission and approval systems fail as two distinct modes: under-enforcement and over-prompting." The trajectory evidence is thinner (root pip warning, process kill lifecycle errors) while the informal evidence is broader (7 convergent issue reports). Neither lane overclaims; the trajectory lane explicitly says it "can promote permission-friction candidates, but not strong claims of robust permission safety."

CWD/workdir findings converge: trajectory lane shows BigAI `/tmp` pathing failure; informal lane shows Windows/UNC path corruption across multiple issue reports.

### Source-to-Literature reconciliation

Status: appropriately separate.

The literature lane's formal claims about schema-typed tools, deferred discovery, and authorization-vs-sandbox separation provide definitional sharpening. The codebase lane's source-backed findings show partial implementation of these patterns (deepagents capability gating, KIRA allow/deny/ask, a-evolve MCP dynamic filtering). The literature lane explicitly preserves the Wave 04 carry-forward: formal richness does not override behavioral evidence. No literature claim is promoted above what source and trajectory evidence supports.

## Lane Closure Assessment Against Lane Closure Criteria

### Trajectory/Failure Lane

- Answered the active wave question about tool gateways, environment handling, and permission boundaries: yes.
- Cites concrete repo-local evidence: yes (11 trajectory files, 2 reconstruction anchors, 2 support artifacts).
- Observation separated from inference: yes (each claim has explicit observation/inference/confidence/weakness).
- `coverage_not_yet_used` is explicit: yes.
- Main analyst wrote the final synthesis: yes (support artifacts are inventories, not promoted synthesis).
- Saturation status assignable: yes (emerging for tool gateway and cwd/workdir; exploratory for permission boundary).
- Per-run analysis for promoted slice: yes (trajectory support matrix covers 11 runs individually).
- Cross-run comparison: yes (cross-family comparisons section, workflow patterns section).
- Pass/fail divergence analysis: yes (failure candidates section with 4 failure categories).
- `behavioral reconstruction` caveats: yes, explicit on all BigAI entries.

Assessment: wave-sufficient for this lane.

### Codebase/Source-Reconstruction Lane

- Answered the active wave question: yes.
- Cites concrete repo-local source paths: yes (extensive per-family paths).
- Observation separated from inference: yes (8 source-backed claims, 2 reconstructions, each with explicit structure).
- `coverage_not_yet_used` is explicit: yes.
- Subsystem mapping: yes (per-family subsystem findings).
- First-class vs secondary separation: yes (claw-code explicitly quarantine/archive pressure).
- Source-system dossier coverage: partially; dossier updates are listed as required but deferred.
- Source/behavior mismatches explicitly handled: yes (3 mismatches documented).

Assessment: wave-sufficient for this lane. Dossier updates should be completed during support-track work, not as a lane blocker.

### Literature/Formal Lane

- Answered the active wave question: yes (7 domain-specific formal claims).
- Active-domain routing into anchor/theme/inventory: yes (two theme dossiers updated).
- Unread papers noted: yes (3 priority sources listed).
- Formal claims tied to active domain: yes.
- Contradictions preserved: yes (formal vs carry-forward baseline tension explicitly noted).

Assessment: wave-sufficient for this lane.

### Informal/Issues/Postmortems Lane

- Answered the active wave question: yes (6 high-signal operating claims).
- Cluster routing across informal/issues/postmortems: yes (4 clusters).
- Contradiction-pressure clusters: yes (sandbox/approval drift, tool-sprawl, browser mismatch, cwd/path).
- Separation between operator philosophy and issue evidence: yes.
- Low-credibility caveats: yes (issue status mixed, vendor concentration, promotional material noted).

Assessment: wave-sufficient for this lane.

## Carry-Forward Caution Enforcement

### Wave 03 cautions (verified as still present)

- BigAI behavioral reconstruction: maintained across all four lanes. Clean.
- Restart/resume under-evidenced: not a Wave 05 target domain, but not silently promoted either. Clean.
- Organizer weak: coverage register still notes `organizer.md` is empty. Maintained.

### Wave 04 cautions (verified as still present)

- Artifact-first baseline: trajectory lane preserves "shell-plus-file tooling with stable cwd/workdir discipline is sufficient to complete core tasks" as W05-T5. Clean.
- Source-capacity vs behavior-exercise gap: codebase lane's mismatch_01 (deepagents source richer than trajectory exercise) and mismatch_02 (KIRA source vs trajectory command errors) both preserve this gap explicitly. Clean.
- Anti-flattening of mechanism families: trajectory lane keeps tool gateway, environment discovery, cwd/workdir, and permission boundaries as separate claims (W05-T1 through W05-T4). Codebase lane separates command-policy, approval, sandbox, and cwd/workdir surfaces. Informal lane maintains four distinct clusters. Clean.

## Coverage Register Consistency

Status: stale but not blocking.

The coverage register currently says "Wave 05 `tools_environment_permissions`: packet prepared, not started." This is factually wrong: all four lanes have substantive outputs and four support artifacts exist. The register must be updated during principal synthesis to reflect Wave 05 execution state.

This is a governance maintenance issue, not a synthesis-quality blocker.

## Missing Artifacts Assessment

### Required case-study path

`tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md` is absent. The brief lists this under `required_case_study_updates`. Both the codebase and trajectory lanes note this gap.

Assessment: the brief also explicitly lists under `what_can_remain_unfinished_without_blocking_contradiction_review`: "dossier polish after the wave if current claims can still cite the support artifacts honestly." The trajectory support matrix covers headless-terminal run-level detail that a case study would formalize. This gap is a support-track completion item, not a synthesis blocker.

### Deferred support artifacts

Several support artifacts were deferred by lanes:
  - trajectory: `trajectory_support_browser_terminal_substrate_table.md`, `trajectory_support_run_to_source_link_map.md`
  - codebase: `codebase_support_approval_boundary_map.md`, `codebase_support_browser_terminal_substrate_map.md`
  - literature: three support clusters
  - informal: three support clusters

Assessment: the deferred artifacts are optional depth, not required infrastructure. The four present support artifacts plus three dossiers provide sufficient evidence scaffolding for first-pass wave acceptance.

### Required dossier updates

All lanes list required dossier updates under `required_dossier_updates`. These are deferred beyond the lane outputs and should be completed as support-track work. The three dossiers that were updated (two literature themes, one informal cluster) are substantive and cited by their lanes.

Source-system dossiers for deepagents, KIRA, a-evolve, BigAI_behavioral, and claw-code are flagged as needing Wave 05 updates. This is support-track work that should happen alongside or after principal synthesis.

```text
- coverage_used:
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/brief.md
  - tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md
  - tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md
  - tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md
  - tracking/collab/stage_02_synthesis/coverage_register/current_status.md
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_failure_analyst.md
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/codebase_source_reconstruction_analyst.md
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/literature_papers_docs_analyst.md
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/informal_issues_postmortems_analyst.md
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_support_tool_environment_matrix.md
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_support_permission_boundary_cases.md
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/codebase_support_tool_gateway_map.md
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/codebase_support_environment_permission_map.md
  - tracking/collab/stage_02_synthesis/literature_dossiers/themes/tool_use_and_gateways.md
  - tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md
  - tracking/collab/stage_02_synthesis/informal_cluster_dossiers/tools_environment_permissions.md
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/contradiction_analyst.md (primary GPT, for resolved-blocker context)
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/contradiction_analyst__gemini.md (Gemini gate, for resolved-blocker context)
- coverage_not_yet_used:
  - optional long-tail trajectory pressure:
    - research/sources/trajectories/*/git-multibranch/*.txt
  - deferred support artifacts from all four lanes
  - unread formal sources flagged by literature lane:
    - research/sources/docs/src_doc_1ebb8bf0aacd/artifact.txt
    - research/sources/docs/src_doc_695f1b9755d4/artifact.txt
    - research/sources/docs/src_doc_78e1a708df4a/artifact.txt
    - research/sources/papers/papers_text/2603.00324.txt
  - unread informal sources flagged by informal lane:
    - research/sources/issues/src_iss_677a876a6ea9/artifact.txt
    - research/sources/issues/src_iss_7ea08b4fb93c/artifact.txt
    - research/sources/issues/src_iss_6bbe542bed6c/artifact.txt
    - research/sources/informal/cursor_cursorbench.md
    - research/sources/informal/anthropic_long_running_harness.md
- evidence_classes_touched:
  - trajectories (via trajectory lane outputs and support artifacts)
  - mirrored codebases (via codebase lane outputs and support artifacts)
  - papers (via literature lane output and theme dossier)
  - docs (via literature lane output and theme dossier)
  - informal sources (via informal lane output and cluster dossier)
  - issues (via informal lane output and cluster dossier)
  - postmortems (via informal lane output and cluster dossier)
  - relevant local analysis (bigai_trace_layer via trajectory and codebase lanes)
  - relevant local harness code (blocks/runner via codebase lane)
  - prior wave synthesis and coverage register
- priority_sources_not_yet_read:
  - research/sources/trajectories/*/git-multibranch/*.txt (optional long-tail cwd/worktree pressure)
  - research/sources/docs/src_doc_1ebb8bf0aacd/artifact.txt
  - research/sources/issues/src_iss_677a876a6ea9/artifact.txt
  - research/sources/informal/anthropic_long_running_harness.md
- support_artifact_gaps:
  - tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md (missing, support-track item)
  - several deferred support artifacts listed above (non-blocking for first-pass wave acceptance)
  - source-system dossier updates deferred for support-track work
- coverage_register_consistency:
  - inconsistent: Wave 05 marked "packet prepared, not started" despite all four lanes having outputs plus four support artifacts.
  - must be corrected during principal synthesis.
  - this is a governance maintenance item, not a synthesis-quality blocker.
- supported_findings:
  - finding_01:
    - observation: three materially different cross-family tool gateway surfaces are visible both in trajectories and in source.
    - inference: tool gateway design is a distinct mechanism family axis that should not be flattened into generic execution control.
    - confidence: high
    - cross-lane reconciliation: trajectory W05-T1 aligns with codebase claims_01/04/06 and codebase_support_tool_gateway_map table.
    - evidence_paths:
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_failure_analyst.md
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/codebase_source_reconstruction_analyst.md
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/codebase_support_tool_gateway_map.md
  - finding_02:
    - observation: cwd/workdir mismatch is a first-order failure boundary with converging trajectory, source, and informal evidence.
    - inference: path discipline should be treated as its own mechanism card.
    - confidence: high
    - cross-lane reconciliation: trajectory W05-T3 and PB-02 align with codebase claims_03/04/07 and informal path/cwd cluster.
    - evidence_paths:
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_failure_analyst.md
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/codebase_source_reconstruction_analyst.md
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/informal_issues_postmortems_analyst.md
  - finding_03:
    - observation: the terminal-first minimal baseline remains empirically valid across required Wave 05 slices.
    - inference: browser/tool prestige should not displace this baseline without stronger trajectory evidence.
    - confidence: high
    - cross-lane reconciliation: trajectory W05-T5 aligns with codebase subsystem findings and informal browser-mismatch cluster caveat.
    - evidence_paths:
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_failure_analyst.md
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/codebase_support_tool_gateway_map.md
  - finding_04:
    - observation: cancellation and interrupt semantics are a recurrent cross-family failure surface.
    - inference: cancellation boundary handling is a stable mechanism candidate in the tools/environment domain.
    - confidence: high
    - cross-lane reconciliation: trajectory W05-T6 and PB-05 converge with informal permission/approval cluster evidence.
    - evidence_paths:
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_failure_analyst.md
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_support_permission_boundary_cases.md
  - finding_05:
    - observation: permission and approval systems show at least two distinct failure surfaces (under-enforcement and over-prompting) converging across informal issue evidence.
    - inference: permission handling should be modeled as bifurcated mechanism surfaces, not a single pass/fail axis.
    - confidence: high (for the existence of the pattern); medium (for cross-system saturation beyond sampled issue trackers).
    - cross-lane reconciliation: informal high-signal claim aligns with codebase source-backed KIRA heterogeneous permission doctrine.
    - evidence_paths:
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/informal_issues_postmortems_analyst.md
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/codebase_source_reconstruction_analyst.md
- unsupported_or_overclaimed_findings:
  - finding_01:
    - observation: environment discovery is claimed as a "recurring precondition mechanism" (trajectory W05-T2, medium confidence) but the trajectory-level evidence is thin: only DeepAgents headless-terminal shows explicit startup environment_context; other families show implicit or absent discovery signals.
    - inference: this claim should remain at medium confidence and not be promoted as a strong cross-family behavior. Source evidence (deepagents local_context, a-evolve SKILL.md) shows capacity but not demonstrated exercise.
    - confidence: medium-low that this is a currently promotable mechanism card vs an exploratory candidate.
    - evidence_paths:
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_failure_analyst.md
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_support_tool_environment_matrix.md
  - finding_02:
    - observation: the literature lane's benchmark-definition notes (MCPAgentBench, Try-Check-Retry) and eval-relevance framing are at the boundary of eval-lane reasoning while the eval lane is inactive.
    - inference: acceptable as non-binding formal-source sharpening only; should not be treated as active eval adjudication.
    - confidence: medium (boundary is respected in current text but could drift in principal synthesis).
    - evidence_paths:
      - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/literature_papers_docs_analyst.md
- missing_evidence_classes:
  - eval/benchmark evidence is structurally absent (fifth lane inactive by packet design; this is expected, not a defect).
  - browser-substrate trajectory evidence is thin in required Wave 05 slices (only KIRA extract-moves `image_read`).
- reconciliation_failures:
  - no hard reconciliation failures detected across the four lanes.
  - soft reconciliation gap: deepagents extract-moves cancel-only trajectory means tool gateway behavior for deepagents is empirically under-tested in that specific task regime.
  - soft reconciliation gap: formal literature's rich approval/authorization doctrine vs trajectory-level absence of end-to-end approval enforcement remains an open tension (not a failure, but a gap to carry forward).
- coverage_blind_spots:
  - BigAI internals remain invisible (structural, not remedial within this wave).
  - organizer routing remains unavailable.
  - a-evolve has no required trajectories in the Wave 05 packet, so its substantial source findings lack direct trajectory reconciliation for this wave.
  - local harness code (`blocks/`, `runner/`) is stubs/interfaces only, making local-harness implications directional rather than reconciled.
- required_repairs_before_acceptance:
  - update coverage register to reflect Wave 05 actual execution state before principal synthesis.
  - ensure principal synthesis carries forward the trajectory-level permission gap (no end-to-end approval-policy observed in required slices).
  - the prior GPT `blocked` verdict was based on a missing trajectory lane that now exists; principal should formally note this resolution.
- optional_pressure_tests:
  - add BigAI cancel-async long-tail trajectories (17f3a357, d7992f9a) to pressure cwd/permission claims (trajectory lane already read them; codebase lane did not but lists them as priority).
  - run optional `git-multibranch` trajectory pressure for cwd/worktree boundary saturation.
  - verify whether browser substrate reliability claims hold outside issue/postmortem pressure in required trajectories (currently very thin).
  - create `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md` as post-wave support-track work.
  - complete source-system dossier updates for Wave 05 domain during support-track work.
- gate_review_recommendations:
  - change verdict from `blocked` (prior GPT/Gemini) to `pass_with_warnings`.
  - the structural blocker (missing trajectory lane) is resolved.
  - all four required lanes are present, substantive, and self-consistent with honest coverage accounting.
  - cross-lane reconciliation is materially achieved for the core promoted families (tool gateway, cwd/workdir, cancellation boundaries).
  - carry-forward warnings must remain explicit:
    - permission safety remains under-evidenced at trajectory level
    - environment discovery is an exploratory mechanism candidate, not yet a strong cross-family behavior
    - deepagents extract-moves cancel-only trajectory weakens family completeness but does not undermine core promoted claims
    - formal-vs-behavioral gap on approval/authorization doctrine must stay visible
    - a-evolve findings are source-backed without Wave 05 trajectory reconciliation
    - BigAI remains behavioral reconstruction
    - organizer control surface remains empty
    - coverage register must be updated
  - keep explicit carry-forward cautions from prior waves:
    - Wave 03: BigAI behavioral reconstruction, restart/resume under-evidenced, organizer weakness
    - Wave 04: artifact-first baseline, source-capacity vs behavior-exercise gap, anti-flattening of mechanism families
  - principal synthesis may proceed with these warnings visible.
  - checklist adjudication should verify that carry-forward warnings are preserved unchanged.
- confidence:
  - high on verdict change from `blocked` to `pass_with_warnings` (structural blocker resolved, all four lanes present and substantive).
  - high on supported findings (cross-lane convergence on tool gateway, cwd/workdir, cancellation, minimal-sufficient baseline).
  - high on BigAI boundary maintenance.
  - medium on permission-trajectory gap assessment (informal evidence is strong, trajectory evidence is thin, formal evidence is normative).
  - medium on environment-discovery mechanism candidate status (source capacity exceeds trajectory exercise).
```
