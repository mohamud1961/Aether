CODEBASE_SUPPORT_ARTIFACT
- artifact: mechanism_map / wave_06_planning_orchestration_and_interactions
- support_type: planner_runtime_map
- purpose: map where planning/replanning/orchestration runtime contracts are explicit in source-visible systems and where they are only behaviorally reconstructed.
- coverage_used:
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py`
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/subagents.py`
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/async_subagents.py`
  - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/session_manager.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/scheduler_runtime.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/scheduler_mcp_tools.py`
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_slack_handlers.py`
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/operator/agent.py`
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/bot_call_detector/agent.py`
  - `research/sources/codebases/a-evolve/agent_evolve/engine/loop.py`
  - `research/sources/codebases/a-evolve/agent_evolve/algorithms/guided_synth/engine.py`
  - `research/sources/codebases/a-evolve/agent_evolve/agents/mcp/agent.py`
  - `research/sources/codebases/a-evolve/agent_evolve/agents/mcp/conversation_manager.py`
  - `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/react_solver.py`
  - `research/sources/codebases/a-evolve/agent_evolve/llm/bedrock.py`
  - `research/sources/codebases/quarantine/claw-code/src/runtime.py`
  - `research/sources/codebases/quarantine/claw-code/src/query_engine.py`
  - `research/sources/codebases/quarantine/claw-code/src/reference_data/tools_snapshot.json`
  - `research/sources/trajectories/deepagents/cobol-modernization/cabb8c07-4d6f-415d-9553-82cd2ca1cc13-traj.txt`
  - `research/sources/trajectories/deepagents/openssl-selfsigned-cert/2114a06b-d435-4ad1-b790-0d0e7558c6df-traj.txt`
  - `research/sources/trajectories/terminus-kira/cobol-modernization/8da60a45-3657-4a7c-99d3-d9f0cf7de3dd-traj.txt`
  - `research/sources/trajectories/terminus-kira/openssl-selfsigned-cert/07019853-bc0d-4433-b366-91a8275acfef-traj.txt`
  - `research/sources/trajectories/deepagents/prove-plus-comm/e4e670dd-4a41-4366-a1ca-fc78daca1471.tar.gz`
  - `research/sources/trajectories/terminus-kira/prove-plus-comm/790cd7ff-9610-46c7-bd4d-b86abf611418.tar.gz`
  - `research/analysis/bigai_trace_layer/output/question_answers.json`
  - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
  - `research/analysis/bigai_trace_layer/output/runs/prove-plus-comm/*.json`
  - `research/analysis/bigai_trace_layer/output/runs/cobol-modernization/*.json`
  - `research/analysis/bigai_trace_layer/output/runs/openssl-selfsigned-cert/*.json`

- runtime_map:
  - family: `deepagents`
    planning_contract_surface:
      - base loop doctrine in `BASE_AGENT_PROMPT`: `Understand -> Act -> Verify`
      - todo list middleware is first-class in main and subagent middleware stacks
    orchestration_runtime:
      - `create_deep_agent()` composes planning/filesystem/subagent/summarization middleware and optional async subagents
      - subagent runtime is tool-mediated (`task`) with per-call isolated state injection
    replanning_surface:
      - prompt-level and tool-level; no explicit hardcoded planner role in sampled source
    lifecycle_controls:
      - supports sync and async subagent execution lifecycles with task tracking via `async_tasks`
    confidence: high

  - family: `KIRA (TerminusKira + KiraClaw + KIRA-Slack)`
    planning_contract_surface:
      - `execute_commands` schema requires `analysis`, `plan`, `commands`
      - `task_complete` is gated with a second-call confirmation protocol
    orchestration_runtime:
      - `SessionLane` queue-backed lifecycle (`queued -> running -> completed/failed`)
      - scheduler runtime creates schedule-driven runs through session manager and channel delivery
      - KIRA-Slack handlers route through multiple role-specialized agents
    replanning_surface:
      - mainly agent-driven inside repeated command cycles and queue reruns; no explicit separate planner module in TerminusKira
    lifecycle_controls:
      - lane worker state, scheduled run metadata, and delivery post-processing
    confidence: high

  - family: `a-evolve`
    planning_contract_surface:
      - orchestration is encoded at loop level (`Solve -> Observe -> Snapshot -> EngineStep -> Snapshot -> Reload`)
      - terminal solver uses ReAct analysis/plan prompt contract and explicit `submit()` termination signal
    orchestration_runtime:
      - evolution-cycle orchestrator is central; in-task role fanout is limited in terminal path
      - MCP path uses tool discovery/filtering and pinned-first-message context protection
    replanning_surface:
      - strong at evolution level (retry/mutate cycles), lighter inside single terminal task loops
    lifecycle_controls:
      - cycle history/metrics + workspace versioning integration
    confidence: high

  - family: `BigAI (behavioral reconstruction)`
    planning_contract_surface:
      - planner-first ordering and `save_plan` behavior visible in run JSON and trajectories
    orchestration_runtime:
      - planner/executor/verifier role packets with conditional multi-executor branching
    replanning_surface:
      - explicit fail-then-replan loops present in required run set
    lifecycle_controls:
      - visible at behavioral level only; hidden scheduler/control code unavailable
    confidence: medium

  - family: `claw-code (quarantine)`
    planning_contract_surface:
      - runtime/query port simulates bounded turn loops and route summaries
      - archived tool snapshots mention planner/verifier/subagent tool names
    orchestration_runtime:
      - current visible runtime is a porting/inventory/reporting substrate, not proven production-equivalent orchestration runtime
    replanning_surface:
      - weakly evidenced in active Python port sources
    lifecycle_controls:
      - turn limits, token budgets, transcript compaction and session persistence are visible
    confidence: low

- cross_family_split:
  - `terminal-first single-agent loop family`:
    - deepagents sampled Wave 06 trajectories
    - terminus-kira sampled Wave 06 trajectories
  - `role-separated planner/executor/verifier family`:
    - BigAI (behavioral reconstruction only)
  - `evolution-cycle orchestration family`:
    - a-evolve source-backed loop orchestration

- cautions:
  - do not collapse planner runtime contracts, delegation boundaries, and verifier governance into one generic "agentic workflow" claim.
  - keep BigAI claims behavioral-only until mirrored source exists.
  - keep claw-code as quarantine archive pressure.
