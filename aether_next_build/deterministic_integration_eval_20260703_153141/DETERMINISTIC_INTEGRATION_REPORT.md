# Deterministic Integration Scenario Report

These scenarios use no model calls, Docker, VM, benchmark task attempt, or official grader.
They exercise the real kernel path with static WorkbenchArchitect configs and scripted solver/verifier hooks.

| scenario | status | key checks | receipt count | verifier calls |
|---|---|---|---:|---:|
| workbench_verifier_repair_loop | completed | active_finding_reached_context=True, artifact_changed_after_finding=True, completed=True, final_content_exact=True, verifier_blocked_first_submit=True | 22 | 3 |
| stable_core_tool_guard | completed | mixed_dispatch_allowed_for_core_tools=True, stable_core_shell_visible=True, status_completed_with_stable_core_tools=True | 9 | 1 |
