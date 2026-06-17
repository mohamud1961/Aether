# HarnessEng Public Repository Master Plan

Status: `AUTHORITATIVE_RESTRUCTURE_PLAN`

Date: 2026-06-15

## 1. Objective

Transform the current research and engineering worktree into a clean,
production-grade, open-source research product that demonstrates:

1. a Python agent runtime and harness;
2. a custom agent evaluation suite;
3. rapid harness variant prototyping and experiments;
4. AI-native engineering workflows, skills, orchestration, and handoffs;
5. curated research, synthesis, case studies, and evidence;
6. disciplined testing, verification, provenance, and publication controls.

The repository is being prepared as a primary application artifact for agentic
engineering and full-stack AI engineering roles. A reviewer should understand
the product, architecture, engineering method, and evidence within five
minutes, without navigating raw run archives or private working history.

## 2. Product Definition

HarnessEng contains three primary products.

### 2.1 Harness

The harness contains the Python agent runtime and the systems that control,
observe, and verify it.

It owns:

- model execution loop;
- tools, MCP integration, permissions, and hooks;
- skills loading and invocation;
- subagent and worker orchestration;
- context engineering and compaction;
- environment mapping and EnvContract;
- jobs, sessions, and service monitoring;
- evidence ledger and verifier blockers;
- observable decision traces and receipts;
- task completion semantics;
- CLI and runner control surfaces.

### 2.2 Eval Suite

The eval suite evaluates agent behavior independently of the runtime.

It owns:

- custom behavioral evals;
- homolog task families;
- deterministic graders and visible verifiers;
- targeted boards and calibration boards;
- score rows and scoreboard contracts;
- contamination controls;
- baselines, ceilings, known-bad cases, and sentinels;
- eval adapters without redistributed eval corpora.

### 2.3 AI-Native Engineering Workflows

The workflow layer documents and packages the engineering system used to build
the harness.

It owns:

- reusable skills;
- goal, planning, review, and closeout procedures;
- orchestrator and worker handoff protocols;
- run analysis and causal failure diagnosis;
- deep research synthesis;
- model routing and review gates;
- variant and eval governance;
- evidence inventory and publication procedures.

## 3. Final Public Repository Tree

```text
harnesseng/
  README.md
  START_HERE.md
  QUICKSTART.md
  ARCHITECTURE.md
  AI_NATIVE_WORKFLOW.md
  CASE_STUDIES.md
  EVALS.md
  VARIANTS.md
  SECURITY.md
  CONTRIBUTING.md
  AGENTS.md
  LICENSE
  NOTICE
  pyproject.toml
  .gitignore

  harness/
    README.md
    aether2/
      __init__.py

      runtime/
        bridge_harbor.py
        context.py
        executor.py
        jobs.py
        model_client.py
        sessions.py

      control/
        loop.py
        compactor.py
        escalation.py
        prompts.py
        model_routing.py
        handoffs.py

      tools/
        schemas.py
        registry.py
        native.py
        mcp.py
        permissions.py

      skills/
        loader.py
        registry.py
        invocation.py

      hooks/
        registry.py
        lifecycle.py
        builtins.py

      agents/
        task.py
        worker.py
        subagents.py
        orchestrator.py

      env/
        orientation.py
        env_contract.py
        grader_isolation.py

      monitoring/
        cleanup_accounting.py
        metrics.py
        run_phase_journal.py
        service_monitor.py

      verification/
        verify.py
        blockers.py
        evidence_ledger.py

      traces/
        delta.py
        envelope.py
        mirror.py
        receipts.py
        decision_trace.py

      cli/
        run.py
        demo.py

    tools/
      genericity_check.py
      targeted_board.py
      scoreboard.py

  eval_suite/
    README.md
    schemas/
    graders/
    adapters/
    custom/
      artifact_truth/
      environment_contract/
      fake_progress/
      interactive_sessions/
      long_running_jobs/
      package_installation/
      service_persistence/
    boards/
      custom_behavioral_board.yaml
      targeted_board.yaml
      calibration_board.yaml
    fixtures/
    sentinels/
    scoreboards/
      curated/

  variants/
    README.md
    families/
      context_management/
      evidence_and_completion/
      service_monitoring/
      verifier_semantics/
    shared/
    scoreboards/
    hypothesis_backlog.md

  experiments/
    README.md
    configs/
    results/
      curated/

  workflows/
    README.md
    skills/
      orchestration/
        goal_planning_and_review_closeout/
        worker_handoff_writing/
      analysis/
        analyze_agent_runs/
        evidence_inventory_and_synthesis_prep/
        trace_causality_and_fake_progress_analysis/
      eval/
        eval_design_and_variant_governance/
      ops/
        git_commit_slicing_and_handoff/
      publishing/
        public_repo_curation_and_hiring_packaging/
    orchestration/
      governed_multi_agent_model.md
      principal_agent_workflow.md
      handoff_protocol.md
      model_routing.md
      overnight_team_loop.md
      review_gates.md
    synthesis/
      synthesis_handbook.md
      evidence_inventory.md
      deep_synthesis_workflow.md
    schemas/
      failure_card.md
      mechanism_card.md
      task_packet.md
      trajectory_case_study.md
      variant_family_seed.md

  research/
    README.md
    synthesis/
      deep_synthesis_summary.md
      failure_taxonomy.md
      mechanism_map.md
      eval_implications.md
    case_studies/
      agent_harness.md
      loop_engineering.md
      unsupported_completion.md
      variant_prototyping.md
    methodology/
      source_intake.md
      trajectory_analysis.md
      evidence_and_causality.md

  docs/
    README.md
    architecture/
      system_overview.md
      agent_runtime.md
      harness_control_plane.md
      env_contract.md
      verification_and_ledger.md
      service_monitoring.md
      observable_decision_traces.md
    evidence/
      public_run_summary.md
      custom_eval_scoreboard.md
      verifier_grader_disagreement.md
      trace_sample.md
    publication/
      redaction_policy.md
      provenance_audit.md
      source_provenance.md
      third_party_licenses.md

  tests/
    harness/
      runtime/
      control/
      tools/
      env/
      monitoring/
      verification/
      traces/
      integration/
    eval_suite/
    workflows/

  scripts/
    README.md
    build_runtime_bundle.sh
    configure_vm_autoshutdown.sh
    deallocate_vm.sh
    deploy_worker_runtime.sh

  website/
    README.md
    package.json
    src/
    public/
```

## 4. Current-To-Target Map

### 4.1 Aether-2 Core

| Current path | Target path |
|---|---|
| `runner/aether2/bridge_harbor.py` | `harness/aether2/runtime/bridge_harbor.py` |
| `runner/aether2/context.py` | `harness/aether2/runtime/context.py` |
| `runner/aether2/executor.py` | `harness/aether2/runtime/executor.py` |
| `runner/aether2/jobs.py` | `harness/aether2/runtime/jobs.py` |
| `runner/aether2/model_client.py` | `harness/aether2/runtime/model_client.py` |
| `runner/aether2/sessions.py` | `harness/aether2/runtime/sessions.py` |
| `runner/aether2/loop.py` | `harness/aether2/control/loop.py` |
| `runner/aether2/compactor.py` | `harness/aether2/control/compactor.py` |
| `runner/aether2/escalation.py` | `harness/aether2/control/escalation.py` |
| `runner/aether2/prompts.py` | `harness/aether2/control/prompts.py` |
| `runner/aether2/tools.py` | split under `harness/aether2/tools/` |
| `runner/aether2/orientation.py` | split into `harness/aether2/env/orientation.py` and `env_contract.py` |
| `runner/aether2/cleanup_accounting.py` | `harness/aether2/monitoring/cleanup_accounting.py` |
| `runner/aether2/metrics.py` | `harness/aether2/monitoring/metrics.py` |
| `runner/aether2/verify.py` | split under `harness/aether2/verification/` |
| `runner/aether2/delta.py` | split between `traces/delta.py` and `verification/evidence_ledger.py` |
| `runner/aether2/envelope.py` | `harness/aether2/traces/envelope.py` |
| `runner/aether2/mirror.py` | `harness/aether2/traces/mirror.py` |
| `runner/aether2/receipts.py` | `harness/aether2/traces/receipts.py` |
| `tools/aether2_decision_trace.py` | `harness/aether2/traces/decision_trace.py` plus CLI shim |
| `tools/aether2_grader_isolation.py` | `harness/aether2/env/grader_isolation.py` plus CLI shim |
| `tools/aether2_genericity_check.py` | `harness/tools/genericity_check.py` plus CLI shim |
| `tools/aether2_targeted_board.py` | `harness/tools/targeted_board.py` plus CLI shim |
| `tools/run_phase_journal.py` | `harness/aether2/monitoring/run_phase_journal.py` plus compatibility import |

`runner.aether2.*` and current `tools/*.py` entrypoints remain as compatibility
shims during migration. They are removed only after tests, scripts, and public
documentation use the new package.

### 4.2 Features Adapted Into The Python Runtime

The final runtime remains Python. Relevant headless agent-runtime mechanisms
will be adapted into Aether rather than porting an entire TypeScript product.

Include:

- query and turn lifecycle;
- tool and permission registries;
- MCP tool discovery and invocation;
- skills discovery, loading, and invocation;
- lifecycle hooks;
- local subagents and worker tasks;
- run/session state;
- context and memory loading;
- headless configuration;
- streaming/tool-call normalization;
- abort, limits, usage, and cost accounting.

Leave out:

- interactive React/Ink UI;
- themes, keybindings, animations, and product UX;
- voice, dream, and experimental modes;
- cloud coordinator and complex remote runtime;
- product telemetry;
- vendor-specific branding and configuration;
- plugin marketplace UX;
- interactive permission dialogs;
- full REPL and terminal presentation features.

### 4.3 Eval Suite

| Current source | Public target |
|---|---|
| `evals/*.py` | `eval_suite/` generic metrics/contracts |
| clean task definitions from `tracking/collab/aether2_g2_homologs/` | `eval_suite/custom/` |
| clean fake-progress definitions | `eval_suite/custom/fake_progress/` |
| board schemas/manifests from final harness eval suite | `eval_suite/schemas/` and `boards/` |
| deterministic grader interfaces | `eval_suite/graders/` |
| eval adapter code | `eval_suite/adapters/` |
| selected redacted scoreboards | `eval_suite/scoreboards/curated/` |

Do not copy raw run directories, hidden truth, reviewer packs, evidence tarballs,
host workspaces, absolute paths, or eval answer material.

### 4.4 Variants And Experiments

The current `tracking/variants/` tree is an evidence archive, not the public
variant package.

Public variants are rebuilt from selected code and configs:

- package by mechanism family;
- include source/config, README, hypothesis, sentinel, and sanitized result;
- preserve keep/kill rationale;
- exclude raw run directories, logs, receipts, and host state;
- distinguish experimental variants from promoted runtime behavior.

### 4.5 Workflows And Skills

| Current source | Public target |
|---|---|
| `tracking/collab/skills/analyze-agent-runs/` | `workflows/skills/analysis/analyze_agent_runs/` |
| `GOVERNED_MULTI_AGENT_OPERATING_MODEL.md` | `workflows/orchestration/governed_multi_agent_model.md` |
| `PRINCIPAL_AGENT_WORKFLOW.md` | `workflows/orchestration/principal_agent_workflow.md` |
| `SYNTHESIS_PREP_CHECKLIST.md` and `SYNTHESIS_TEAM_SPEC.md` | `workflows/synthesis/synthesis_handbook.md` |
| card and packet schemas at root | `workflows/schemas/` |
| reusable prompt content from `prompts/` | colocated with the relevant skill or workflow |
| raw build handoffs and thread summaries | private; derive case studies only |

Public `AGENTS.md` becomes a concise contributor and agent-operation index. It
must not contain private machine paths, current campaign state, credential
details, or temporary orchestration instructions.

### 4.6 Research And Documentation

Curate into public research:

- deep synthesis conclusions;
- failure taxonomy;
- mechanism map;
- eval implications;
- source-intake methodology;
- trajectory analysis methodology;
- selected redacted case studies;
- variant decision methodology.

Keep private:

- `research/sources/`;
- `research/intake/`;
- raw trajectories;
- captured papers/docs/issues;
- external repository mirrors;
- quarantined codebases;
- raw synthesis working directories;
- private source location maps.

## 5. Public, Private, Archive, And Generated Boundaries

### 5.1 Never Publish

```text
official_tasks/
tracking/ledger/
tracking/variants/
tracking/collab/**/runs/
tracking/collab/**/workspaces/
tracking/collab/**/host_workspace/
tracking/collab/**/workspace_fixture/
tracking/collab/vm_pulls/
research/sources/
research/intake/
research/external/
scratch/
.playwright-mcp/
.venv/
venv/
.pytest_cache/
website/node_modules/
website/.next/
repomix-output.xml
output/
*.log
*.tar.gz
*.zip
.DS_Store
```

This list is a publication default, not a deletion list. Private evidence must
be backed up outside the public repository before restructuring.

### 5.2 Curate, Do Not Publish Raw

- ledger history;
- Codex/Claude thread transcripts;
- worker handoffs;
- VM run bundles;
- result rows with host paths;
- model exchanges;
- receipts;
- source snapshots;
- eval trajectories;
- internal plans and self-critique.

Safe public substitutes:

- milestone summaries;
- anonymized decision records;
- sanitized scoreboards;
- redacted trace excerpts;
- generalized case studies;
- reusable skills and schemas.

### 5.3 Archive

Archive rather than promote:

- `runner/packet03_*`;
- `runner/packet07_*`;
- `runner/successor_*`;
- `runner/phase15_measurement_repair.py`;
- `mlpcp_v2_complete_variant_package_expanded_docs/`;
- `p4r1/`;
- `p4r2/`;
- superseded campaign plans.

The archive may remain in private history or a separate archival branch. It
should not dominate the public default branch.

## 6. Migration Strategy

### Phase 0: Freeze And Protect

1. Record current branch, status, and file inventory.
2. Back up the entire dirty worktree and private evidence.
3. Restore and document license/provenance files.
4. Create publication branch.
5. Add privacy exclusions before broad staging.
6. Run secret and oversized-file scans.

Exit criteria:

- recoverable backup exists;
- private paths cannot be staged accidentally;
- provenance decisions are recorded;
- no destructive move has occurred.

### Phase 1: Public Skeleton

Create:

- root public docs;
- `harness/`;
- `eval_suite/`;
- `variants/`;
- `workflows/`;
- curated `research/`;
- `docs/`;
- test namespaces.

Do not move implementation yet.

Exit criteria:

- target architecture is documented;
- each directory has a short README;
- public/private boundary is explicit.

### Phase 2: Harness Compatibility Migration

1. Create new Python package namespaces.
2. Move one coherent module family at a time.
3. Keep old import paths as re-export shims.
4. Move or duplicate focused tests with each family.
5. Keep current CLIs as stable wrappers.
6. Run focused and broad tests after every slice.

Recommended order:

1. traces and receipts;
2. environment and grader isolation;
3. verification and evidence ledger;
4. runtime execution modules;
5. control loop and prompts;
6. monitoring and metrics;
7. tools, skills, hooks, MCP, and subagents;
8. CLI integration.

### Phase 3: Eval Suite Extraction

1. Promote generic eval contracts.
2. Export clean custom behavioral evals.
3. Build public boards and schemas.
4. Generate sanitized scoreboards.
5. Verify hidden truth and raw runs are absent.

### Phase 4: Workflow And Research Curation

1. Publish `analyze_agent_runs`.
2. Build the orchestration and handoff skills.
3. Rewrite governance docs as public methodology.
4. Distill deep synthesis and case studies.
5. Publish provenance and redaction policies.

### Phase 5: Variant Gallery

1. Select representative mechanism families.
2. Extract clean code/configs.
3. Add hypotheses and sentinels.
4. Add sanitized keep/kill evidence.
5. Clearly mark promoted, experimental, and retired variants.

### Phase 6: Product And Hiring Surface

1. Rewrite README and START_HERE.
2. Add architecture diagrams.
3. Add role-relevant case studies.
4. Replace website boilerplate.
5. Add CI, formatting, typing, test commands, and security checks.
6. Validate a clean clone.

## 7. Testing And Quality Gates

Every migration slice must satisfy:

- existing focused tests pass;
- compatibility imports pass;
- no eval-specific knowledge enters generic runtime code;
- no private path appears in committed files;
- no raw run artifact is added;
- public docs match the current tree;
- new modules have docstrings and stable boundaries;
- public CLI entrypoints have `--help`;
- secret and large-file scans pass.

Final gates:

```text
unit tests
integration tests
custom behavioral evals
genericity check
grader-isolation tests
public-tree privacy scan
license/provenance audit
clean-clone installation
clean-clone test run
```

## 8. Commit Strategy

Commit real historical work in logical, reviewable slices. Do not manufacture
commit volume or split changes solely to alter contribution statistics.

Suggested sequence:

1. publication policy and privacy exclusions;
2. license and provenance;
3. public skeleton and docs;
4. harness trace migration;
5. environment migration;
6. verification migration;
7. runtime migration;
8. control-loop migration;
9. MCP, skills, hooks, and subagents;
10. eval suite extraction;
11. workflow skills;
12. curated research;
13. variants;
14. website and hiring surface;
15. final cleanup and CI.

Each commit should:

- contain one coherent ownership boundary;
- include relevant tests or docs;
- avoid mixing raw archival data with product code;
- explain compatibility behavior;
- leave the repository runnable.

## 9. Decisions Resolved

1. The public implementation is Python.
2. The agent runtime and harness live together under `harness/`.
3. The eval suite is a separate top-level product.
4. AI-native engineering workflows are a separate top-level product.
5. Variants remain public, but only as curated mechanism families.
6. Research remains public only as curated synthesis and methodology.
7. The raw ledger remains private.
8. Raw source mirrors and task corpora remain private.
9. Existing import paths remain temporarily compatible.
10. The restructuring is incremental and test-gated, not a big-bang rewrite.

## 10. Open Decisions Before Implementation

1. Final public project name: `HarnessEng`, `Aether`, or another umbrella name.
2. Whether `Aether-2` remains the runtime name or becomes the whole platform.
3. Exact upstream provenance record for adapted runtime mechanisms.
4. Whether the website ships in the first public release.
5. Which three variant families and which custom eval families are the first
   public showcase set.
6. Whether legacy code lives on an archive branch or in a private repository.
7. Whether public compatibility shims are retained for one release or longer.

## 11. Immediate Next Action

Before moving files, execute Phase 0:

1. create a full backup;
2. finalize `.gitignore` and publication exclusions;
3. write the provenance and redaction documents;
4. run secret and large-file inventories;
5. produce a staged-file allowlist;
6. only then begin the public skeleton and compatibility migration.

