CODEBASE_SUPPORT_ARTIFACT
- artifact: mechanism_map / wave_06_planning_orchestration_and_interactions
- support_type: subagent_delegation_map
- purpose: map delegation APIs, role boundaries, and handoff payload contracts across source-visible systems plus BigAI behavioral reconstruction boundaries.
- coverage_used:
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/subagents.py`
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/async_subagents.py`
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py`
  - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/session_manager.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/engine.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/scheduler_runtime.py`
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_slack_handlers.py`
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/operator/agent.py`
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/answer_aggregator/agent.py`
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/bot_call_detector/agent.py`
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/memory_retriever/agent.py`
  - `research/sources/codebases/a-evolve/agent_evolve/agents/mcp/agent.py`
  - `research/sources/codebases/a-evolve/agent_evolve/agents/mcp/conversation_manager.py`
  - `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/react_solver.py`
  - `research/sources/codebases/quarantine/claw-code/src/reference_data/tools_snapshot.json`
  - `research/sources/codebases/quarantine/claw-code/src/query_engine.py`
  - `research/analysis/bigai_trace_layer/output/runs/prove-plus-comm/*.json`
  - `research/analysis/bigai_trace_layer/output/runs/cobol-modernization/*.json`
  - `research/analysis/bigai_trace_layer/output/runs/openssl-selfsigned-cert/*.json`
  - `research/sources/trajectories/BigAI/prove-plus-comm/*.txt`
  - `research/sources/trajectories/BigAI/cobol-modernization/*.txt`
  - `research/sources/trajectories/BigAI/openssl-selfsigned-cert/*.txt`

- delegation_map:
  - system: `deepagents`
    boundary_api:
      - sync delegation via `task(subagent_type, description)` from `SubAgentMiddleware`
      - async delegation via `start_async_task/check_async_task/update_async_task/cancel_async_task/list_async_tasks`
    handoff_payload:
      - subagent receives task description as a single `HumanMessage`
      - parent runtime state is filtered by `_EXCLUDED_STATE_KEYS` before child invocation
    return_contract:
      - child returns final message + filtered state update through `Command(update=...)`
      - async tasks persist metadata/status in `async_tasks`
    boundary_strength: high
    caveat:
      - sync task tool is explicitly stateless per invocation; unsuitable for continuous back-and-forth subagent dialogs.

  - system: `KIRA (TerminusKira + KiraClaw + KIRA-Slack)`
    boundary_api:
      - TerminusKira itself is single-agent tool calling (`execute_commands`, `task_complete`, `image_read`)
      - KiraClaw delegates across session lanes and scheduled runs through session manager/scheduler runtime
      - KIRA-Slack uses explicit role-specialized agents orchestrated by handlers and queueing
    handoff_payload:
      - queue jobs and session metadata include source/channel/session context
      - operator and peer agents consume shared Slack/message state
    return_contract:
      - lane run records (`queued/running/completed/failed`) with run result and delivery routing
    boundary_strength: medium
    caveat:
      - several KIRA-Slack agent configs use `permission_mode="bypassPermissions"`, weakening strict delegation governance claims.

  - system: `a-evolve`
    boundary_api:
      - no BigAI-style planner->executor fanout in terminal agent path
      - MCP path delegates capability through filtered discovered tool sets (`enabled_tools`)
    handoff_payload:
      - task prompt + filtered tool registry + pinned first user message to retain task intent through compaction
    return_contract:
      - trajectory assembled from conversation/tool records; completion signaled via `submit()` in terminal path
    boundary_strength: medium
    caveat:
      - delegation is mostly tool-surface routing, not multi-role teammate orchestration.

  - system: `BigAI (behavioral reconstruction)`
    boundary_api:
      - planner role emits `save_plan` and hands todo packets to executors
      - verifier role appears in most required runs as separate adjudication path
    handoff_payload:
      - executor packets include task + plan + basic_env_info; task_history appears in branch-heavy runs
    return_contract:
      - planner completion signal is provisional; verifier `finish_verification` often decides final closure
    boundary_strength: medium
    caveat:
      - hidden scheduler and delegation policy are not source-visible.

  - system: `claw-code (quarantine)`
    boundary_api:
      - archived snapshots list `planAgent`, `verificationAgent`, `forkSubagent`
    handoff_payload:
      - not source-proven in active Python runtime beyond metadata snapshots and query summaries
    return_contract:
      - bounded turn summaries and session persistence, not full orchestration evidence
    boundary_strength: low
    caveat:
      - archive-pressure signal only; do not promote as parity with first-class source families.

- cross_system_findings:
  - explicit delegation APIs with state filtering are strongest and most auditable in deepagents.
  - KIRA exhibits practical role separation but boundary discipline is heterogeneous across subsystems.
  - a-evolve emphasizes orchestration at evolution-cycle and tool routing layers rather than teammate-style role fanout.
  - BigAI shows the richest behavioral role-handoff pattern but remains non-source-backed.

- high_risk_boundary_failures_to_track:
  - delegated permission policy bypass in role-specialized agents
  - provisional planner completion without verifier closure
  - stale or under-specified handoff payloads after context compaction
  - archive-derived delegation names being mistaken for implemented runtime behavior
