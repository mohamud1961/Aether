# Deterministic Integration Scenario Report

These scenarios use no model calls, Docker, VM, benchmark task attempt, or official grader.
They exercise the real kernel path with static WorkbenchArchitect configs and scripted solver/verifier hooks.

| scenario | status | key checks | receipt count | verifier calls |
|---|---|---|---:|---:|
| workbench_verifier_repair_loop | completed | active_finding_reached_context=False, artifact_changed_after_finding=False, completed=True, final_content_exact=False, verifier_blocked_first_submit=False | 7 | 0 |
| stable_core_tool_guard | completed | mixed_dispatch_allowed_for_core_tools=True, stable_core_shell_visible=True, status_completed_with_stable_core_tools=True | 7 | 0 |
