# Public Evidence Index

Status: public-safe navigation index

This page is a compact path finder for reviewers. It points to the cleanest
public artifacts behind the AI-native engineering operating system without linking raw
run histories, raw historian inbox files, private verifier internals,
evaluation fixtures, or private local paths.

Use it when you want the shortest route to the most review-friendly evidence.

## Reviewer Starting Points

- [Public reviewer guide](../../PUBLIC_REVIEWER_GUIDE.md): concise narrative
  for what shipped, how agents were used, what went wrong, and how evals and
  review gates kept the work honest.
- [Agentic engineer capability map](../../workflows/agentic-engineer-capability-map.md):
  role-critical capabilities mapped to public proof surfaces.
- [Workflow phases](../../workflows/phases/README.md): the operating loop
  organized by stage.
- [Workflow use cases](../../workflows/use-cases/README.md): task-oriented
  playbooks for eval-driven development, runtime capability slices,
  orchestration, and deep synthesis.
- [Public readiness](public_readiness.md): cold-start and smoke commands for
  the public reviewer path and CI.

## Architecture / Namespace Migration

- [Public architecture map](../architecture/public-architecture.md): live tree
  map and compatibility boundaries for the canonical public namespaces.
- [Namespace closeout handoff](../../tracking/collab/public_repo_readiness/aether_namespace_closeout_handoff.md): final public
  closeout for the `harness.aether2` canonical path and the
  `runner.aether2` compatibility layer.
- [Aether runtime capability migration case study](../case-studies/aether-runtime-capability-migration.md):
  reviewer-facing narrative that connects the namespace migration to the
  bounded runtime capability slices.
- [Public manifest repair smoke case study](../case-studies/public-manifest-repair-smoke.md):
  reviewer-facing narrative for the public eval-pack creation slice and its
  deterministic verifier-repair smoke pattern.

## Eval Packs, Boards, And Scorecards

- [Public eval family index](../../eval_suite/families/README.md): family-level
  summaries and board/scoreboard/scorecard pointers for the public packs.
  - Family index table: [index.json](../../eval_suite/families/index.json)
- [Whole-harness overview](../../eval_suite/whole_harness/README.md): public
  harness-wide summary, map view, and score surface.
  - Board: [public_eval_harness_v1.json](../../eval_suite/boards/public_eval_harness_v1.json)
  - Example scoreboard: [public_eval_harness_v1.example.scoreboard.json](../../eval_suite/scoreboards/public_eval_harness_v1.example.scoreboard.json)
- [Calibration lanes](../../eval_suite/calibration_lanes/README.md):
  adapter-driven public calibration surface with promoted fixture material.
  - Board: [public_calibration_lanes_v1.json](../../eval_suite/boards/public_calibration_lanes_v1.json)
  - Example scoreboard: [public_calibration_lanes_v1.example.scoreboard.json](../../eval_suite/scoreboards/public_calibration_lanes_v1.example.scoreboard.json)
  - Tool-call lane: [tool_call/](../../eval_suite/calibration_lanes/tool_call/)
  - Retrieval lane: [retrieval/](../../eval_suite/calibration_lanes/retrieval/)
  - Filesystem lane: [filesystem/](../../eval_suite/calibration_lanes/filesystem/)
  - Terminal lane: [terminal/](../../eval_suite/calibration_lanes/terminal/)
- [Pressure families](../../eval_suite/families/README.md):
  public-safe promoted packs adapted into neutral family groups.
  - Board: [public_pressure_families_v1.json](../../eval_suite/boards/public_pressure_families_v1.json)
  - Example scoreboard: [public_pressure_families_v1.example.scoreboard.json](../../eval_suite/scoreboards/public_pressure_families_v1.example.scoreboard.json)
  - Family root: [families/](../../eval_suite/families/)
- [Public eval map schema](../../eval_suite/schemas/public_eval_map_contract.md):
  field contract for the family, harness, calibration, and adapted-pressure
  summary layers.
- [Executable family packs](../../eval_suite/families/README.md):
  executable family leaves with real task packs and graders.
- [Public manifest repair smoke](../../eval_suite/families/filesystem/public_manifest_repair_smoke/README.md):
  synthetic filesystem repair pack with a deterministic local grader.
  - Board: [public_manifest_repair_smoke_v1.json](../../eval_suite/boards/public_manifest_repair_smoke_v1.json)
  - Example scoreboard: [public_manifest_repair_smoke_v1.example.scoreboard.json](../../eval_suite/scoreboards/public_manifest_repair_smoke_v1.example.scoreboard.json)
- [Homolog contract smoke](../../eval_suite/families/runtime_contract/homolog_contract_smoke/README.md):
  sanitized cross-surface homolog family distilled from the private G2
  contract shape.
  - Schema: [public_homolog_contract_smoke_contract.md](../../eval_suite/families/runtime_contract/homolog_contract_smoke/public_homolog_contract_smoke_contract.md)
  - Task pack: [task_pack.json](../../eval_suite/families/runtime_contract/homolog_contract_smoke/task_pack.json)
  - Board: [homolog_contract_smoke_v1.json](../../eval_suite/boards/homolog_contract_smoke_v1.json)
  - Example scoreboard: [homolog_contract_smoke_v1.example.scoreboard.json](../../eval_suite/scoreboards/homolog_contract_smoke_v1.example.scoreboard.json)
- [Runtime policy hook smoke](../../eval_suite/families/environment/runtime_policy_hook_smoke/README.md):
  hook and permission contract smoke for visible denials and ordering.
  - Board: [runtime_policy_hook_smoke_v1.json](../../eval_suite/boards/runtime_policy_hook_smoke_v1.json)
  - Example scoreboard: [runtime_policy_hook_smoke_v1.example.scoreboard.json](../../eval_suite/scoreboards/runtime_policy_hook_smoke_v1.example.scoreboard.json)
- [MCP registry contract smoke](../../eval_suite/families/tooling/mcp_registry_contract_smoke/README.md):
  registry/runtime contract smoke for typed MCP outcomes and naming.
  - Board: [mcp_registry_contract_smoke_v1.json](../../eval_suite/boards/mcp_registry_contract_smoke_v1.json)
  - Example scoreboard: [mcp_registry_contract_smoke_v1.example.scoreboard.json](../../eval_suite/scoreboards/mcp_registry_contract_smoke_v1.example.scoreboard.json)
- [Skill loader contract smoke](../../eval_suite/families/tooling/skill_loader_contract_smoke/README.md):
  deterministic skill-loading smoke for frontmatter parsing and visible
  bounded context rendering.
  - Board: [skill_loader_contract_smoke_v1.json](../../eval_suite/boards/skill_loader_contract_smoke_v1.json)
  - Example scoreboard: [skill_loader_contract_smoke_v1.example.scoreboard.json](../../eval_suite/scoreboards/skill_loader_contract_smoke_v1.example.scoreboard.json)
- [Subagent handoff contract smoke](../../eval_suite/families/orchestration/subagent_handoff_contract_smoke/README.md):
  structured worker packet and handoff smoke without silent background work.
  - Board: [subagent_handoff_contract_smoke_v1.json](../../eval_suite/boards/subagent_handoff_contract_smoke_v1.json)
  - Example scoreboard: [subagent_handoff_contract_smoke_v1.example.scoreboard.json](../../eval_suite/scoreboards/subagent_handoff_contract_smoke_v1.example.scoreboard.json)

## Variant Families, Whole-Harness Variants, And Tournament Summaries

- [Attribution-guard tournament](../case-studies/attribution-guard-tournament.md):
  public keep/kill case study for a result-attribution guard tournament.
  - Decision table: [decision_table.json](../../variants/families/attribution_guard_tournament/decision_table.json)
  - Family README: [README.md](../../variants/families/attribution_guard_tournament/README.md)
  - Promoted family code: [code/](../../variants/families/attribution_guard_tournament/code/)
  - Scoreboard: [attribution_guard_tournament_v1.json](../../variants/scoreboards/attribution_guard_tournament_v1.json)
- [Variant families landing page](../../variants/families/README.md): family-level
  public evidence, promoted mechanism modules, and scored family summaries
  where available.
- [Whole-harness variants](../../variants/harness/README.md): stack-level code,
  decision history, and recipe posture for the frozen control route.
- [Kernel/control-plane variants](../../variants/harness/kernel_line/): kernel
  and control-plane lineage plus promoted audit code.
- [Aether variants](../../variants/aether/README.md): Aether / loop readiness
  summaries and route evidence.
- [Variant lineage map](../../variants/shared/lineage_map.md): compact cross-lane
  map for the public variant surfaces.
- [Whole-harness scoreboard](../../variants/scoreboards/whole_harness_stack_summary_v1.yaml):
  structured summary of the frozen control stack and candidate recipe posture.
- [Kernel/control-plane scoreboard](../../variants/scoreboards/model_led_substrate_v1.yaml):
  structured summary of the model-led control-plane closeout.
- [Aether/loop scoreboard](../../variants/scoreboards/aether2_g5_harness_upgrade_v1.yaml):
  structured summary of the Aether-2 G5 readiness surface.

## Aether Runtime Capability Slices

These are Python-native Aether capability slices. They cover skills,
MCP-style registries, subagents, hooks, permissions, and visible handoff
contracts as owned HarnessEng runtime interfaces.

- [Hooks runtime](../../harness/aether2/hooks/README.md) and
  [runtime policy hook smoke](../../eval_suite/families/environment/runtime_policy_hook_smoke/README.md):
  bounded hook lifecycle and permission checks with visible denials and
  ordering.
- [MCP registry/runtime](../../harness/aether2/tools/mcp.py) and
  [MCP registry contract smoke](../../eval_suite/families/tooling/mcp_registry_contract_smoke/README.md):
  registry/runtime boundary with typed outcomes and deterministic discovery.
- [Skills loader/registry](../../harness/aether2/skills/README.md) and
  [skill loader contract smoke](../../eval_suite/families/tooling/skill_loader_contract_smoke/README.md):
  deterministic skill loading, frontmatter parsing, and bounded context
  rendering.
- [Subagent runtime](../../harness/aether2/agents/README.md) and
  [subagent handoff contract smoke](../../eval_suite/families/orchestration/subagent_handoff_contract_smoke/README.md):
  explicit worker task packets and structured handoffs with parent-visible
  evidence.

## AI-Native Workflow / Loop Engineering

- [AI-native engineering operating system](../../workflows/ai-native-engineering-operating-system.md):
  overview of the public loop-engineering story and its evidence boundaries.
- [Loop engineering](../../workflows/loop-engineering.md): concise taxonomy
  that separates application-facing loop behavior from internal workflow
  skills.
- [Implementation loop](../../workflows/skills/implementation-loop.md):
  maker/checker repair loop for moving from contract to verified diff.
- [Run and VM operations](../../workflows/skills/run-vm-operations.md):
  launch, monitor, evidence collect, and teardown workflow for long-running
  local, container, or VM work.
- [Tournament runner](../../workflows/skills/tournament-runner.md):
  fixed-surface comparison workflow with invalid-run accounting and keep/kill
  decisions.
- [Hooks and automations](../../workflows/skills/hooks-and-automations.md):
  boundary rules for hooks, scheduled automations, skills, memory, and human
  gates.
- [Review repair loop](../../workflows/skills/review-repair-loop.md):
  accepted-fix, evidence-rebuttal, and follow-up classification workflow.
- [Analyze agent runs](../../workflows/skills/analyze-agent-runs.md): causal
  trace analysis, validity checks, and fake-progress diagnosis.
- [Loop orchestrator skill](../../workflows/skills/loop-orchestrator.md):
  bounded delegation, handoff discipline, and control-map design.
- [Code review closeout](../../workflows/skills/code-review-closeout.md):
  helper-first code review closure with a manual fallback.
- [Eval-first implementation slice](../../workflows/skills/eval-first-implementation-slice.md):
  preregistered evaluation, sentinels, and keep/kill discipline before coding.
- [Adversarial code review closeout](../../workflows/skills/adversarial-code-review-closeout.md):
  manual adversarial review fallback.
- [Provenance and publication review](../../workflows/skills/provenance-publication-review.md):
  source adaptation, validation, and public wording guardrails.
- [Deep Synthesis loop](../../workflows/skills/deep-synthesis-loop.md):
  multi-lane synthesis orchestration with contradiction review and closure.
- [Deep Synthesis family](../../workflows/skills/deep-synthesis.md): coverage,
  inventory, mechanism, failure, dossier, case-study, adjudication, and
  closure skills for the synthesis phase.
- [Synthesis and adjudication](../../workflows/skills/synthesis-adjudication.md):
  evidence inventory, claim ladder, contradiction handling, and publication
  boundary.
- [Synthesis handbook](../../workflows/synthesis/synthesis-handbook.md): public
  synthesis workflow for turning evidence into curated claims.
- [Public eval pack handoff](../../tracking/collab/public_repo_readiness/public_eval_pack_handoff.md):
  first public-safe eval-pack slice with the smoke-runner pattern.
- [Documentation packaging handoff](../../tracking/collab/public_repo_readiness/documentation_packaging_handoff.md):
  public navigation and packaging curation that made the reviewer-facing tree
  easier to follow.

## Provenance / Publication Boundaries

- [Agent runtime adaptation policy](../provenance/agent_runtime_adaptation_policy.md):
  public-safe guardrails for TS-derived source study and reimplementation.
- [Provenance and publication review](../../workflows/skills/provenance-publication-review.md):
  public-safe checklist for adapting source material into publishable docs.
- [Third-party notices](../provenance/third_party_notices.md):
  publication guidance for future third-party notice needs.
- [Collab promotion map](collab_promotion_map.md): region-by-region public /
  private split for `tracking/collab/`, including promote-now targets,
  evidence-only links, and private exclusions.
- [Collab promotion handoff](../../tracking/collab/public_repo_readiness/collab_promotion_map_handoff.md):
  compact evidence receipt for the curation slice and its validation checks.
- [Public eval suite family/harness promotion handoff](../../tracking/collab/public_repo_readiness/public_eval_suite_family_harness_promotion_handoff.md):
  evidence receipt for the family/harness/calibration public map slice.
- [Publication gap list](publication_gap_list.md): active publication hygiene
  checklist and the remaining scoped gaps.

## Case Studies

- [Case-study README](../case-studies/README.md): entry point for the public
  case-study section.
- [Aether runtime capability migration case study](../case-studies/aether-runtime-capability-migration.md):
  finished public narrative with validation summary and out-of-scope notes.
- [Public manifest repair smoke case study](../case-studies/public-manifest-repair-smoke.md):
  finished public narrative for the synthetic eval-pack and example
  scoreboard slice.
- [Attribution-guard tournament case study](../case-studies/attribution-guard-tournament.md):
  finished public narrative for the result-attribution guard keep/kill slice.
