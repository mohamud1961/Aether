# Deterministic Integration Scenario Report

These scenarios use no model calls, Docker, VM, benchmark task attempt, or official grader.
They exercise the real kernel path with static WorkbenchArchitect configs and scripted solver/verifier hooks.

| scenario | status | key checks | receipt count | verifier calls |
|---|---|---|---:|---:|
| workbench_verifier_repair_loop | completed | active_finding_reached_context=True, artifact_changed_after_finding=True, completed=True, final_content_exact=True, verifier_blocked_first_submit=True | 16 | 2 |
| disabled_tool_guard | completed | disabled_shell_rejected=False, invalid_turn_prevented_mixed_dispatch=False, status_incomplete_without_allowed_repair_turn=False | 8 | 1 |
