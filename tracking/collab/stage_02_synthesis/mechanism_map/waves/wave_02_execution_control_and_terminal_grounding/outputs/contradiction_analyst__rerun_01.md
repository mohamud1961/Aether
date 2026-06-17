DEEP_SYNTHESIS_CONTRADICTION_OUTPUT
- artifact: mechanism_map
- rerun_scope:
  - this is a same-wave contradiction rerun after `trajectory_failure_analyst__followup_01.md` and `codebase_source_reconstruction_analyst__followup_01.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/contradiction_analyst.md` is treated as historical context only, not the final contradiction judgment for the strengthened packet
  - adjudication question: whether the same-wave follow-ups closed the main Wave 02 warnings enough for checklist adjudication
  - changed_since_original_contradiction:
    - the trajectory lane now includes packet-required per-run analysis, shared-task cross-system comparison, pass/fail divergence analysis, failure-point comparison, source reconciliation where source exists, and selective archive rescue
    - the source lane now deepens `claw-code`, `src_cod_*`, KIRA session-adjacent internals where visible, and family placement pressure from `autoagent`
    - the main remaining defects are no longer “missing depth” defects; they are narrower reconciliation and saturation warnings
  - can_wave_02_now_proceed_to_checklist_adjudication: yes, but only as `pass_with_warnings`
- preflight_scope_confirmed:
  - yes: this remains a vertical mechanism-domain wave for `execution_control_and_terminal_grounding`, not a source-only or trajectory-only pass
  - yes: trajectories remain the primary empirical anchor, and this rerun judges whether the follow-ups closed the packet-required depth enough for checklist-facing use
  - yes: BigAI remains constrained to `behavioral reconstruction` unless new source appears
  - simple contender kept visible: a discrete command-and-file loop remains live beside session and role-separated controllers, visible in `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst__followup_01.md`, `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/local_shell.py`, and `research/sources/codebases/autoagent/agent.py`
- preflight_planned_read_order:
  1. reread the shared policy, contradiction prompt, execution protocol, workflow guide, active wave brief, follow-up plan, and current wave synthesis surfaces
  2. reread the five primary wave outputs plus the two same-wave follow-up outputs and the original contradiction file as historical context
  3. inspect support artifacts that the trajectory follow-up depends on for pass/fail and failure-point claims
  4. spot-check raw trajectory bundles and raw source only where the follow-ups materially change the earlier contradiction judgment
  5. decide whether the remaining defects are still structural blockers or only adjudication-stage warnings
- preflight_critical_sources_selected:
  - governance and rerun framing:
    - `prompts/deep_synthesis_shared_policy_prompt.md`
    - `prompts/deep_synthesis_contradiction_analyst_prompt.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/brief.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/brief.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/inputs/lane_followup_plan.md`
  - wave synthesis context:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/synthesis/principal_synthesis.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - lane outputs:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/literature_papers_docs_analyst.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/informal_issues_postmortems_analyst.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/eval_benchmark_analyst.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst__followup_01.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst__followup_01.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/contradiction_analyst.md`
  - support artifacts and direct pressure checks:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_support_pass_fail_matrix.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_support_failure_points.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_support_source_links.md`
    - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz`
    - `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef.tar.gz`
    - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
    - `research/analysis/bigai_trace_layer/output/runs/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.json`
    - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/{process_tools.py,process_manager.py,session_manager.py}`
    - `research/sources/codebases/deepagents/libs/evals/deepagents_harbor/{backend.py,deepagents_wrapper.py}`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/{backends/local_shell.py,graph.py}`
    - `research/sources/codebases/deepagents/libs/deepagents/tests/unit_tests/backends/test_local_shell_backend.py`
    - `research/sources/codebases/quarantine/claw-code/src/{runtime.py,query_engine.py,execution_registry.py,remote_runtime.py,commands.py,tools.py}`
    - `research/sources/codebases/src_cod_086db5a6312e/artifact.zip`
    - `research/sources/codebases/src_cod_87b73c75d11a/artifact.zip`
    - `research/sources/codebases/src_cod_c7b08f87aeac/artifact.zip`
    - `research/sources/codebases/autoagent/{agent.py,program.md}`
- preflight_coverage_risks:
  - BigAI still has no visible source in this corpus, so the strengthened wave can only keep BigAI at `behavioral reconstruction`
  - the codebase follow-up materially improved `src_cod_*` pressure, but my rerun spot-check only verified a subset of the claimed archive families directly
  - repo-state-safe cleanup is much better evidenced than in the original contradiction pass, but it is still more trajectory-heavy than source/eval-reconciled
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/synthesis/principal_synthesis.md` and `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md` predate the follow-up depth and should be treated as historical context during adjudication
- preflight_likely_blind_spots:
  - deeper unread archive members inside some `src_cod_*` captures, especially beyond the few runtime files spot-checked here
  - low-level Harbor `Terminus2` or `TmuxSession` implementation files not mirrored in the captured corpus
  - benchmark-side implementation traces behind the known verifier mismatches
  - remaining unread paired DeepAgents and Terminus-KIRA bundles for the selected task families
- preflight_blockers: []
- overall_verdict: pass_with_warnings
- coverage_used:
  - policy and workflow:
    - `prompts/deep_synthesis_shared_policy_prompt.md`
    - `prompts/deep_synthesis_contradiction_analyst_prompt.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
  - packet and synthesis context:
    - `tracking/collab/stage_02_synthesis/mechanism_map/brief.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/brief.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/inputs/lane_followup_plan.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/synthesis/principal_synthesis.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - wave outputs:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/literature_papers_docs_analyst.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/informal_issues_postmortems_analyst.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/eval_benchmark_analyst.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst__followup_01.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst__followup_01.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/contradiction_analyst.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_support_pass_fail_matrix.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_support_failure_points.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_support_source_links.md`
  - direct raw bundle checks:
    - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz`
    - `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef.tar.gz`
    - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
    - `research/analysis/bigai_trace_layer/output/runs/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.json`
  - direct source checks:
    - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_tools.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_manager.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/session_manager.py`
    - `research/sources/codebases/deepagents/libs/evals/deepagents_harbor/backend.py`
    - `research/sources/codebases/deepagents/libs/evals/deepagents_harbor/deepagents_wrapper.py`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/local_shell.py`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py`
    - `research/sources/codebases/deepagents/libs/deepagents/tests/unit_tests/backends/test_local_shell_backend.py`
    - `research/sources/codebases/quarantine/claw-code/src/{runtime.py,query_engine.py,execution_registry.py,remote_runtime.py,commands.py,tools.py}`
    - `research/sources/codebases/src_cod_086db5a6312e/artifact.zip`
    - `research/sources/codebases/src_cod_87b73c75d11a/artifact.zip`
    - `research/sources/codebases/src_cod_c7b08f87aeac/artifact.zip`
    - `research/sources/codebases/autoagent/agent.py`
    - `research/sources/codebases/autoagent/program.md`
- coverage_not_yet_used:
  - unread paired selected-family bundles under `research/sources/trajectories/deepagents/*/*.tar.gz` and `research/sources/trajectories/terminus-kira/*/*.tar.gz` beyond the rerun spot-checks above
  - `research/sources/codebases/src_cod_e231561a3d69/artifact.zip` and deeper long-tail members from the other `src_cod_*` captures were not directly re-spot-checked in this rerun
  - non-mirrored Harbor internals behind KIRA imports:
    - `harbor.agents.terminus_2.terminus_2`
    - `harbor.agents.terminus_2.tmux_session`
  - benchmark implementation code behind `research/sources/benchmarks/src_bnm_*/artifact.html`
  - any mirrored primary source for BigAI
- evidence_classes_touched:
  - wave governance and workflow artifacts
  - wave synthesis surfaces
  - trajectory outputs and support artifacts
  - raw trajectory bundles
  - mirrored source code
  - archive source captures (`artifact.zip`)
  - eval-side first-pass analysis
  - literature/docs first-pass analysis
  - informal/issues/postmortems first-pass analysis
- priority_sources_not_yet_read:
  - `research/sources/trajectories/{deepagents,terminus-kira,BigAI}/{git-multibranch,db-wal-recovery,break-filter-js-from-html}/*.tar.gz` beyond the few rerun spot-checks already made
  - `research/sources/codebases/src_cod_e231561a3d69/artifact.zip`
  - deeper `artifact.zip` members inside the other `src_cod_*` captures not directly re-opened in this rerun
  - `research/sources/codebases/langchain/agentevals/**`
  - non-mirrored Harbor `Terminus2` and `TmuxSession` implementation files
  - any newly captured primary BigAI source if it appears later
- supported_findings:
  - finding: The trajectory follow-up closes the main trajectory-depth warning enough for checklist adjudication.
    observation: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst__followup_01.md` adds per-run analysis across the five shared families, explicit shared-task cross-system comparison, pass/fail divergence analysis, failure-point comparison, source reconciliation notes, and selective archive rescue. The support artifacts and raw bundles directly confirm the strongest divergence runs: DeepAgents `cancel-async-tasks` fails `5/6`, DeepAgents `break-filter-js-from-html` fails `0/1`, Terminus-KIRA `db-wal-recovery` ends with `reward: 0` and `AgentTimeoutError`, and BigAI `cancel-async-tasks` shows the internal-versus-external mismatch in raw files.
    inference: the wave no longer has a structural trajectory-depth defect of the kind flagged by `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/inputs/lane_followup_plan.md`.
    evidence: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst__followup_01.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_support_pass_fail_matrix.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_support_failure_points.md`, `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz`, `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef.tar.gz`, `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz`, `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`, `research/analysis/bigai_trace_layer/output/runs/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.json`
    confidence: high
  - finding: The codebase follow-up closes the main source-depth warning enough to support the family split that Wave 02 was already converging toward.
    observation: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst__followup_01.md` deepens KIRA session-adjacent code, DeepAgents Harbor/runtime boundaries, constrains `claw-code` to mirrored scaffolding, opens `artifact.zip` archive families beyond `capture.json`, and explicitly places `autoagent` with the discrete command family. My rerun spot-checks confirm KIRA marker-based tmux/session control, DeepAgents timeout-bounded discrete host execution, claw-code placeholder remote/runtime surfaces, Codex PTY/pipe control paths inside `command_exec.rs`, Agentsh interactive PTY protocol, OpenHands stuck-loop detection, and `autoagent`'s single `run_shell` tool.
    inference: the wave now has enough visible source pressure to justify the current multi-family mechanism framing and to reject the earlier risk of relying on `capture.json` or partial ports alone.
    evidence: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst__followup_01.md`, `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`, `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/{process_tools.py,process_manager.py,session_manager.py}`, `research/sources/codebases/deepagents/libs/evals/deepagents_harbor/{backend.py,deepagents_wrapper.py}`, `research/sources/codebases/deepagents/libs/deepagents/deepagents/{backends/local_shell.py,graph.py}`, `research/sources/codebases/quarantine/claw-code/src/{runtime.py,query_engine.py,execution_registry.py,remote_runtime.py,commands.py,tools.py}`, `research/sources/codebases/src_cod_87b73c75d11a/artifact.zip`, `research/sources/codebases/src_cod_c7b08f87aeac/artifact.zip`, `research/sources/codebases/src_cod_086db5a6312e/artifact.zip`, `research/sources/codebases/autoagent/{agent.py,program.md}`
    confidence: medium-high
    weakness: my rerun spot-check confirmed only a subset of the archive families claimed in the follow-up, so this is strong enough for contradiction closure but not a license to treat every archive pressure family as fully saturated
  - finding: The follow-ups preserve the distinct family split rather than collapsing KIRA, DeepAgents-like systems, and BigAI into one generic terminal harness.
    observation: the trajectory follow-up and source follow-up keep KIRA as session/tmux control, DeepAgents plus a-evolve plus autoagent as discrete command-and-file or command-exec controllers, and BigAI as role-separated only at the behavioral layer. The source follow-up also introduces archive-only pressure families from `src_cod_*`, but leaves them exploratory and not in-wave trajectory-coupled.
    inference: the principal risk of over-flattening the domain has been materially reduced by the follow-ups.
    evidence: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst__followup_01.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst__followup_01.md`, `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`, `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/local_shell.py`, `research/sources/codebases/autoagent/agent.py`
    confidence: high
  - finding: The completion model remains correctly split into internal verifier state, external grader/test artifacts, and eval/judge layers.
    observation: the eval sidecar already required a three-layer completion split, and the trajectory follow-up plus raw BigAI bundle make that split unavoidable: the trace records `finish_verification` / `verification_result_status: PASSED`, while the bundle records `reward: 0.0` with `5 passed / 1 failed`.
    inference: the follow-ups strengthened this earlier warning into a checklist-ready contradiction that should remain explicit in the wave’s accepted state.
    evidence: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/eval_benchmark_analyst.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst__followup_01.md`, `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`, `research/analysis/bigai_trace_layer/output/runs/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.json`
    confidence: high
  - finding: Wave 02 can now proceed to checklist adjudication.
    observation: the lane follow-up plan explicitly required same-wave follow-up output when packet depth was still missing, and the workflow guide says follow-ups are the governed way to move an under-covered lane toward sufficiency. The two actual follow-up files materially address the trajectory and source gaps that the original contradiction and the pre-follow-up principal synthesis still carried forward.
    inference: the wave is no longer blocked on missing same-wave depth; checklist adjudication is now the correct next governed step, but it should inherit the remaining warnings below rather than erase them.
    evidence: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/inputs/lane_followup_plan.md`, `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst__followup_01.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst__followup_01.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/synthesis/principal_synthesis.md`
    confidence: high
- unsupported_or_overclaimed_findings:
  - finding: BigAI is still overclaimed if described as source-backed or as a proven PTY substrate.
    observation: the follow-up trajectory lane keeps BigAI explicitly at `behavioral reconstruction`, the codebase follow-up still reports no primary BigAI source, and the literature/docs lane only provides provider-stated intent.
    inference: the strengthened packet supports BigAI as a behaviorally useful comparison family, not as a source-backed controller family.
    evidence: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst__followup_01.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst__followup_01.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/literature_papers_docs_analyst.md`
    confidence: high
  - finding: The new `src_cod_*` pressure families should not be promoted to core Wave 02 mechanism families as though they had in-wave trajectory reconciliation.
    observation: the codebase follow-up uses archive reads to surface exploratory families such as policy-mediated PTY/exec gateways and streaming command-exec managers, but those families are not paired with same-wave trajectory evidence in this packet.
    inference: they are valid contradiction pressure and future-wave inputs, not settled Wave 02 mechanism cards.
    evidence: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst__followup_01.md`, `research/sources/codebases/src_cod_87b73c75d11a/artifact.zip`, `research/sources/codebases/src_cod_c7b08f87aeac/artifact.zip`, `research/sources/codebases/src_cod_086db5a6312e/artifact.zip`
    confidence: medium-high
    weakness: this is a boundary judgment about how far to promote archive pressure, not a claim that the follow-up misread the raw files
  - finding: Repo-state-safe cleanup is stronger than in the original contradiction pass, but still not equally closed with terminal control and cancellation.
    observation: the trajectory follow-up now directly analyzes `git-multibranch`, `db-wal-recovery`, and cleanup-sensitive `break-filter-js-from-html` runs, but the source follow-up still says repo-state safety often emerges from trajectory-level cleanup and verification behavior rather than a universal source abstraction, and the eval sidecar did not directly sample those bundles.
    inference: the warning narrows from “thin evidence” to “asymmetric evidence,” but it does not disappear.
    evidence: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst__followup_01.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst__followup_01.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/eval_benchmark_analyst.md`
    confidence: medium
    weakness: the remaining asymmetry is about source/eval saturation, not about whether repo-state hygiene matters at all
  - finding: Support artifacts and historical synthesis files should not be over-read as final truth surfaces.
    observation: the trajectory support files explicitly mark themselves as support artifacts only, and the principal/cumulative synthesis files still describe the pre-follow-up state where same-wave follow-up work was still pending.
    inference: checklist adjudication should use the follow-up outputs and this rerun contradiction, not treat either the support addenda or the pre-follow-up principal/cumulative surfaces as the current final judgment.
    evidence: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_support_failure_points.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_support_source_links.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/synthesis/principal_synthesis.md`, `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
    confidence: high
  - finding: Organizer presence is still not usable as a coverage-quality signal.
    observation: both the earlier contradiction pass and the follow-up-governance files had to work around an empty organizer surface in this checkout.
    inference: coverage claims should continue to rest on enumerated files actually read, not on organizer rhetoric.
    evidence: `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/contradiction_analyst.md`
    confidence: medium
    weakness: this is a coverage-accounting caution more than a mechanism-level contradiction
- reconciliation_failures:
  - issue: BigAI still contributes only behavioral reconstruction, while KIRA and DeepAgents now have materially stronger source reconciliation.
    observation: the follow-up outputs deepen KIRA and DeepAgents source pressure substantially, but no same-wave BigAI source appears.
    inference: cross-family synthesis is now strong enough for checklist review, but still asymmetric in how directly each family is source-backed.
    evidence: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst__followup_01.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst__followup_01.md`
    confidence: high
  - issue: Internal verifier status and final graded outcome still diverge, and the exact cause of the divergence remains unresolved.
    observation: the raw BigAI bundle and raw trace show `verification_result_status: PASSED` alongside `reward: 0.0` and `5 passed / 1 failed`, and the raw DeepAgents `cancel-async-tasks` bundle shows the same failing above-max-concurrency cleanup case externally.
    inference: the wave now establishes the contradiction clearly, but does not yet explain the full causal path inside the verifier/controller stack.
    evidence: `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`, `research/analysis/bigai_trace_layer/output/runs/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.json`, `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz`
    confidence: high
  - issue: KIRA session control is source-backed, but low-level Harbor session semantics remain one layer indirect.
    observation: the rerun confirmed marker polling, session liveness checks, and session/process management in the mirrored KIRA code, but the underlying Harbor `TmuxSession` and `Terminus2` implementation files are not in the current capture.
    inference: KIRA’s family placement is strong enough for checklist review, but not fully closed at the lowest implementation layer.
    evidence: `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`, `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/{process_tools.py,process_manager.py,session_manager.py}`
    confidence: medium-high
    weakness: the missing Harbor files are outside the captured mirror, not a contradiction inside the visible KIRA code
  - issue: Repo-state-safe cleanup is now clearly real but still unevenly evidenced across families and evidence classes.
    observation: the trajectory follow-up makes repo sanitation and cleanup visible in `git-multibranch`, `db-wal-recovery`, and `break-filter-js-from-html`, yet the strongest explicit negative and recovery signals remain concentrated in BigAI and one Terminus-KIRA failure-heavy run.
    inference: the mechanism family is real enough to survive contradiction pressure, but not saturated enough to be treated as equally established with terminal interaction and cancellation cleanup.
    evidence: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst__followup_01.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst__followup_01.md`, `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz`
    confidence: medium
    weakness: the packet is now good enough for adjudication, but not yet enough for `decision_ready` saturation on this family
- required_repairs_before_acceptance:
  - checklist adjudication should use this rerun contradiction file together with `trajectory_failure_analyst__followup_01.md` and `codebase_source_reconstruction_analyst__followup_01.md`, not the original contradiction file alone
  - any accepted Wave 02 summary should keep these warnings explicit:
    - BigAI remains `behavioral reconstruction`
    - completion stays three-layered
    - archive-only `src_cod_*` pressure families are exploratory and not in-wave trajectory-backed
    - repo-state-safe cleanup remains less saturated than terminal control and cancellation cleanup
  - the pre-follow-up principal/cumulative synthesis surfaces should be refreshed or explicitly superseded before final artifact acceptance so they do not continue to represent “follow-up still needed” as the current state
- optional_pressure_tests:
  - directly open more selected-family DeepAgents and Terminus-KIRA bundles if checklist adjudication wants stronger raw-bundle pressure beyond the rerun spot-checks
  - inspect benchmark-side traces or verifier-controller internals for the known internal-versus-external mismatch cases
  - deepen direct archive spot-checking for `src_cod_e231561a3d69/artifact.zip` and additional members from the other `src_cod_*` captures if the adjudicator wants stronger archive-family pressure
  - read Harbor `Terminus2` or `TmuxSession` if those files enter the local capture later
- confidence:
  - medium-high for `pass_with_warnings`
  - strongest support: the follow-up trajectory depth is real, the follow-up source depth is real, family separation is materially better grounded, and the internal-versus-external completion split is directly visible in raw evidence
  - weakening factors: BigAI remains source-opaque, some archive-family pressure is still selective, repo-state-safe cleanup is still asymmetrically evidenced, and the current principal/cumulative synthesis files are historical context rather than post-follow-up final state
