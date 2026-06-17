# Claude-Inspired Feature Plan Handoff

- Status: COMPLETE
- Source thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Worker role: `Claude-Inspired Feature Planning Worker 8`
- Date: `2026-06-15`

## Objective And Scope Completed

- Produced a concrete, license-aware, Python-native implementation plan for
  adding selected external agent-runtime capabilities to Aether after the
  public namespace and first eval-pack cleanup.
- Audited the current public Aether surface, workflow materials, and likely
  local Claude-related research copies.
- Did not implement runtime behavior changes.
- Added one concise provenance-policy note only:
  `docs/provenance/agent_runtime_adaptation_policy.md`.

## Files Changed And Ownership Boundaries

- Changed:
  - `docs/provenance/agent_runtime_adaptation_policy.md`
  - `tracking/collab/public_repo_readiness/claude_inspired_feature_plan_handoff.md`
- Not changed:
  - `harness.aether2` runtime, control, tool, trace, eval, workflow, and test
    code.
- Unrelated dirty-tree changes were preserved.

## Verified Inputs

- Found:
  - `AGENTS.md`
  - `README.md`
  - `docs/architecture/public-architecture.md`
  - `tracking/collab/public_repo_readiness/publication_master_plan.md`
  - `tracking/collab/public_repo_readiness/documentation_packaging_handoff.md`
  - `tracking/collab/public_repo_readiness/public_eval_pack_handoff.md`
  - `tracking/collab/public_repo_readiness/aether_namespace_closeout_handoff.md`
  - `harness/aether2/` and its README files
  - `workflows/`
  - `tracking/collab/skills/analyze-agent-runs/`
- Found but qualified:
  - `research/sources/codebases/quarantine/claude-code_ts_release/README.md`
    is missing in the working tree, but present in the nested git `HEAD`.
- Not found as live local provenance files during this slice:
  - a discoverable `LICENSE` or `NOTICE` file in
    `research/sources/codebases/quarantine/claude-code_ts_release/`
  - a discoverable `LICENSE` or `NOTICE` file in
    `research/sources/codebases/quarantine/claw-code/`
  - a discoverable `LICENSE` or `NOTICE` file near the local installed Claude
    app/binary artifacts under `~/Library/Application Support/Claude/`

## Current Aether Surface Relevant To This Plan

- Canonical implemented code is still concentrated in:
  - `harness/aether2/runtime/`
  - `harness/aether2/control/loop.py`
  - `harness/aether2/tools/native.py`
  - `harness/aether2/traces/`
- Public navigation stubs still exist for:
  - `harness/aether2/agents/`
  - `harness/aether2/env/`
  - `harness/aether2/hooks/`
  - `harness/aether2/monitoring/`
  - `harness/aether2/skills/`
  - `harness/aether2/verification/`
- Existing useful primitives already present:
  - explicit tool schema and dispatch boundary in `harness/aether2/tools/native.py`
  - context prefix and tail telemetry in `harness/aether2/runtime/context.py`
  - env contract snapshotting in `harness/aether2/runtime/orientation.py`
  - job/session persistence in `harness/aether2/runtime/jobs.py` and
    `harness/aether2/runtime/sessions.py`
  - evidence ledger and no-progress tracking in `harness/aether2/traces/delta.py`
    and `harness/aether2/traces/mirror.py`
  - verifier and bounded service monitoring logic in
    `harness/aether2/runtime/verify.py` and `harness/aether2/control/loop.py`

## Source And Provenance Inventory

| Path | What it appears to be | Evidence observed | Reuse status | Caveat |
| --- | --- | --- | --- | --- |
| `research/sources/codebases/quarantine/claude-code_ts_release/` | quarantined nested git research copy with TypeScript source layout | local nested `.git`; source dirs including `src/hooks`, `src/skills`, `src/tools`, `src/server`, `src/coordinator`; remote configured as `yasasbanukaofficial/claude-code`; nested `HEAD:README.md` describes a mirror of exposed Claude Code source | concept study only | no live `LICENSE`/`NOTICE` found in checkout used here; direct code reuse blocked |
| `research/sources/codebases/quarantine/claw-code/` | separate nested git rewrite/port project | local nested `.git`; README describes a rewrite/port and disclaims ownership of original Claude source | reference only for framing risks, not authority source | no live `LICENSE`/`NOTICE` found during this slice; derivative project is not provenance authority |
| `~/Library/Application Support/Claude/claude-code/<version>/claude.app` | installed app bundle | local bundle files only; no discoverable license metadata nearby in this slice | not suitable for source reuse | binary/app artifact, not a repo-local source provenance bundle |
| `~/Library/Application Support/Claude/claude-code-vm/<version>/claude` | installed Linux VM binary | `file` reports ELF aarch64 executable | not suitable for source reuse | binary artifact with no repo-local license note found |
| `~/Desktop/*/.claude/settings.json` | per-project tool settings | JSON only, no code | exclude from provenance basis | config only, not source |

### License Caveat

- The user previously verified licensing verbally, but this worker slice did
  not confirm repo-local live license files in the actual research copies being
  cited.
- Result: direct code reuse must be treated as blocked in this repo until a
  repo-local provenance bundle records the exact source, exact license file, and
  any required attribution/notice obligations.
- Concept-level Python reimplementation can still proceed.

## Feature Selection Table

| Feature family | Decision | Public-portfolio value | Implementation risk | Eval required before implementation | Likely files touched | Can be done without source-copying | Provenance note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MCP/tool-server boundary | INCLUDE NOW | high | medium-high | fake local MCP server discovery and call contract smoke; schema translation sentinel | `harness/aether2/tools/`, `harness/aether2/control/loop.py`, `harness/aether2/runtime/context.py`, tests, `eval_suite/custom/` | yes | use concept-level adapter design only |
| Skills loader/registry/invocation | INCLUDE NOW | high | medium | skill-discovery and instruction-injection smoke; no hidden prompt mutation sentinel | `harness/aether2/skills/`, `harness/aether2/runtime/context.py`, `harness/aether2/runtime/prompts.py`, tests, `eval_suite/custom/` | yes | borrow only the idea of repo-local skills, not file formats verbatim |
| Hooks/lifecycle events | INCLUDE NOW | high | medium | hook ordering and no-side-effect contract smoke | `harness/aether2/hooks/`, `harness/aether2/tools/`, `harness/aether2/control/loop.py`, tests, `eval_suite/custom/` | yes | generic event bus pattern is clean-room implementable |
| Permissions/safety policy | INCLUDE NOW | high | medium-high | allow/deny policy smoke; denied-action evidence sentinel | `harness/aether2/tools/permissions.py`, `harness/aether2/control/loop.py`, `harness/aether2/runtime/executor.py`, tests, `eval_suite/custom/` | yes | must be Aether-owned policy language and receipts |
| Session/context lifecycle hardening | INCLUDE NOW | high | medium | continuation/handoff smoke; compaction integrity sentinel | `harness/aether2/runtime/context.py`, `harness/aether2/runtime/compactor.py`, `harness/aether2/runtime/prompts.py`, tests, `eval_suite/custom/` | yes | use owned handoff schema and evidence ledger |
| Env mapping and service monitoring package split | INCLUDE NOW | high | medium | env-contract consistency smoke; bounded service truth sentinel | `harness/aether2/env/`, `harness/aether2/monitoring/`, `harness/aether2/runtime/orientation.py`, `harness/aether2/control/loop.py`, tests, `eval_suite/custom/` | yes | mostly extraction/hardening of existing Aether behavior |
| Memory/handoff/procedural context | INCLUDE LATER | medium-high | high | long-horizon handoff custom smoke; stale-memory regression sentinel | `harness/aether2/skills/`, `harness/aether2/runtime/context.py`, `harness/aether2/traces/`, tests, `eval_suite/custom/` | yes | keep bounded and evidence-backed; do not copy "dream" systems |
| Subagent/thread orchestration interface | INCLUDE LATER | high | high | explicit worker-handoff custom smoke; ownership-boundary sentinel | `harness/aether2/agents/`, `harness/aether2/control/`, tests, `eval_suite/custom/` | yes | should be explicit delegation only, not a copied swarm stack |
| Provider internals/auth/telemetry | EXCLUDE | low | high | none | none | not relevant | do not mirror proprietary infra surfaces |
| Claude UI/Ink terminal app structure | EXCLUDE | low | high | none | none | not relevant | TypeScript UI is not the target product |
| Branding/product names/persona systems | EXCLUDE | negative | low | none | none | yes, by omission | no Claude affiliation or naming in public surfaces |
| Autonomous background planning agents, "dreams", or always-on watchers | EXCLUDE FOR NOW | medium if oversold, low if omitted | high | would need a dedicated safety board later | none in first phase | yes, but should not be first wave | not needed to prove AI-native engineering now |

## Proposed Python-Native Architecture

### Design Rule

Keep the Aether principle intact:

> The model pilots. The harness instruments. The verifier reflects. The ledger
> remembers. The grader decides.

That means:

- do not add harness-side planning phases that override the model;
- do not rewrite tool intents into task-specific macros;
- do not treat hooks, permissions, skills, or delegation as hidden control
  planes;
- do expose new boundaries as observable inputs, typed outputs, and receipts.

### Integration Points

1. Tool boundary
   - Keep `harness/aether2/tools/native.py` as the minimal stable contract.
   - Add a registry layer above it, not a second planner.
   - Native, MCP, and future skill-backed tools should all emit the same typed
     observation envelopes and receipts.

2. Hooks boundary
   - Add explicit lifecycle hooks around tool dispatch, verification start/end,
     compaction, task_done, task_blocked, and run closeout.
   - Hooks may observe, annotate, deny, or emit receipts.
   - Hooks must not silently mutate the task contract or fabricate evidence.

3. Permissions boundary
   - Place policy evaluation before executor side effects.
   - Make denials visible to the model as ordinary observations so the model can
     adapt rationally.
   - Record policy decisions in traces/receipts, not in hidden logs only.

4. Skills boundary
   - Load skills as explicit repo-local instruction assets selected by policy
     and surfaced in the model-visible prefix/tail.
   - Skills should act like bounded procedural context, not like hidden agent
     orchestration.

5. Env/monitoring boundary
   - Move the existing env-contract and bounded service-monitoring logic into
     named public packages under `harness/aether2/env/` and
     `harness/aether2/monitoring/`.
   - Preserve current evidence-first semantics: process-up is not proof of task
     success.

6. Subagent boundary
   - If added later, workers should receive an explicit task/handoff object and
     return a structured evidence handoff.
   - No silent background swarms.
   - The parent model remains responsible for asking for delegation and for
     integrating the returned evidence.

## First Implementation Slices In Dependency Order

### Slice 1: Policy And Hook Substrate

- Eval first:
  - `eval_suite/custom/runtime_policy_hook_smoke/`
  - deterministic grader proving:
    - pre/post tool hooks fire in order;
    - denied actions surface visible observations;
    - denied actions do not mutate workspace state;
    - hooks do not rewrite tool arguments.
- Runtime work after eval:
  - add `harness/aether2/hooks/registry.py`
  - add `harness/aether2/hooks/lifecycle.py`
  - add `harness/aether2/hooks/builtins.py`
  - add `harness/aether2/tools/permissions.py`
  - thread decisions through `harness/aether2/control/loop.py`
- Sentinels:
  - `python3 tools/aether2_genericity_check.py`
  - existing public manifest repair smoke to ensure no regression in base tool flow

### Slice 2: Tool Registry And MCP Boundary

- Eval first:
  - `eval_suite/custom/mcp_registry_contract_smoke/`
  - fake local MCP server fixture proving:
    - tool discovery is deterministic;
    - schema mapping is faithful;
    - timeout/error states become typed observations;
    - native tools and MCP tools share receipt format.
- Runtime work after eval:
  - add `harness/aether2/tools/registry.py`
  - add `harness/aether2/tools/mcp.py`
  - update `harness/aether2/tools/__init__.py`
  - lightly integrate with `runtime/context.py` and `control/loop.py`
- Sentinels:
  - native tool-call smoke
  - no task-specific affordance scan

### Slice 3: Skill Loader And Bounded Procedural Context

- Eval first:
  - `eval_suite/custom/skill_loader_contract_smoke/`
  - prove:
    - skill discovery is path-based and deterministic;
    - selected skill text is surfaced to the model visibly;
    - missing skills fail truthfully;
    - no hidden prompt mutation occurs outside recorded context.
- Runtime work after eval:
  - add `harness/aether2/skills/loader.py`
  - add `harness/aether2/skills/registry.py`
  - add `harness/aether2/skills/invocation.py`
  - integrate bounded skill context into `runtime/context.py` and `runtime/prompts.py`
- Sentinels:
  - compaction integrity
  - evidence-ledger preservation

### Slice 4: Env Contract And Service Monitoring Package Split

- Eval first:
  - `eval_suite/custom/env_service_truth_smoke/`
  - prove:
    - env-contract digest remains stable across run and verification;
    - bounded monitoring distinguishes process-up from behavior-up;
    - job/session survival evidence is surfaced cleanly.
- Runtime work after eval:
  - add `harness/aether2/env/env_contract.py`
  - add `harness/aether2/monitoring/service_monitor.py`
  - optionally add `harness/aether2/monitoring/run_phase_journal.py`
  - extract and shrink logic currently split between
    `runtime/orientation.py` and `control/loop.py`
- Sentinels:
  - current jobs/sessions tests
  - verifier/service truth smoke

### Slice 5: Explicit Subagent Handoff Interface

- Eval first:
  - `eval_suite/custom/subagent_handoff_smoke/`
  - prove:
    - worker receives a bounded task packet;
    - worker returns a structured evidence handoff;
    - parent rationally incorporates the handoff;
    - unresolved worker risk remains visible.
- Runtime work after eval:
  - add `harness/aether2/agents/task.py`
  - add `harness/aether2/agents/subagents.py`
  - add `harness/aether2/control/handoffs.py` or equivalent
  - keep this as opt-in explicit delegation only
- Sentinels:
  - no-progress regression
  - long-horizon handoff custom smoke

## Exact Next Dependency-Ready Implementation Slice

- Slice 1: `policy_and_hook_substrate`
- Why next:
  - it creates the smallest extensibility boundary shared by permissions, MCP,
    skills, and later delegation;
  - it can be evaluated with a tiny deterministic smoke before any broad runtime
    expansion;
  - it keeps Aether model-led by making policy/hook outcomes observable instead
    of hidden.

## What To Leave Out Explicitly

- Claude branding, names, mascots, or product-surface references
- Anthropic provider internals, auth flows, analytics, telemetry, and remote
  control-plane behavior
- Ink/terminal UI and TypeScript-specific component architecture
- copied prompt text, leaked policy text, or line-by-line porting
- "always-on" autonomous assistants, dream/memory daemons, undercover modes, or
  employee-specific behaviors
- risky command policies that assume a trusted desktop product rather than an
  eval-governed public harness
- any behavior whose only justification is "Claude did it that way"

## Job-Application Story

This plan supports the portfolio story best when it proves:

- owned Python runtime architecture rather than derivative TypeScript porting;
- eval-first engineering discipline before capability expansion;
- legal/provenance awareness strong enough to avoid contaminating public code;
- instrumented agent-runtime design across tools, permissions, context,
  monitoring, and handoffs;
- truthful public documentation that distinguishes implemented surfaces from
  planned ones.

What not to claim:

- that HarnessEng is a public clone of Claude Code;
- that leaked or mirrored code was reused directly;
- that production-grade autonomy already exists before these slices land and are
  scored.

## Review Gate: Adversarial Only

### Legal/Provenance Reviewer

- Finding:
  - the first draft risked implying that quarantined research copies could be
    used as implementation references without a repo-local license bundle.
- Repair:
  - tightened the reuse rule: no direct code reuse without exact repo-local
    source, exact license path, and any required notice obligations.
- Final position:
  - concept-level reimplementation allowed; direct reuse blocked for now.

### Runtime Architect Reviewer

- Finding:
  - subagent orchestration was initially too early and would have created a
    broad surface before hooks, permissions, and tool registry boundaries were
    stabilized.
- Repair:
  - moved subagents to Slice 5 and made hooks/policy the first dependency-ready
    slice.
- Final position:
  - extensibility and observability come before delegation.

### Hiring Reviewer

- Finding:
  - a "Claude-inspired" storyline can easily sound derivative or like leaked
    code repackaging.
- Repair:
  - shifted the story toward owned Python interfaces, eval governance, and
    provenance discipline, with explicit exclusions for branding and parity
    claims.
- Final position:
  - this demonstrates AI-native engineering judgment if the repo shows evals,
    interfaces, and evidence rather than imitation.

## Validation

- Verified required file/path existence or labeled missing/qualified cases above.
- Did not run eval or full task rows.
- Documentation-only validation to run after edits:
  - `git diff --check`
- Manual path checks performed for the new markdown references:
  - `research/sources/codebases/quarantine/claude-code_ts_release/`
  - `research/sources/codebases/quarantine/claw-code/`
  - `docs/provenance/agent_runtime_adaptation_policy.md`
  - `tracking/collab/public_repo_readiness/claude_inspired_feature_plan_handoff.md`

## Docs/Provenance Artifacts Changed

- Added `docs/provenance/agent_runtime_adaptation_policy.md`
  - purpose: public-safe statement of what can and cannot be adapted from local
    research copies before runtime work begins

## External-State Confirmation

- No eval runs, VM actions, container actions, branch changes, commits,
  pushes, or worktrees were created.
- No process, server, credential home, or session was left running for this
  slice.

## RAW_LEDGER_UPDATE

- Persisted: yes
- Private raw historian input path: `tracking/ledger/inbox/2026-06-15/195029_claude-inspired-feature-planning-worker-8_produce-a-license-aware-python-native-feature-plan-for-external-agent-runtime-capabilities-after-the-public-namespace-and-first-eval-pack-cleanup_83ed011122.md`

## Thread Send

- Target thread ID: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Send result: success (`codex_app.send_message_to_thread` returned `{"threadId":"019eb760-ea75-7af1-8d62-6e3e8cd7ba2a"}`)
