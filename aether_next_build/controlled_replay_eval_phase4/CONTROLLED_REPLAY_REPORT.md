# Controlled Replay Report

Trace-only replay harness over committed Phase 2 checkpoints.
No model calls, solver/task execution, Docker, VM, or benchmark/grader work was performed.

## Summary

| case | trace | step | repeated_actions | files_already_read | no_progress_streak | pending_checks | repair_hints | model_hint_present |
|---|---|---:|---:|---:|---:|---:|---:|---|
| filter-js-from-html | filter-js-from-html.trace.json | 2 | 0 | 1 | 1 | 0 | 0 | false |
| sparql-university | sparql-university.trace.json | 29 | 2 | 1 | 29 | 0 | 0 | false |
| openssl-selfsigned-cert | openssl-selfsigned-cert.trace.json | 29 | 3 | 2 | 28 | 0 | 0 | false |

## Axis Coverage

| axis | status | note |
|---|---|---|
| old_context vs enriched_deterministic_context | pass | pass=3 evidence_limited=0 |
| preset/basic context vs context recipe/structured memory evidence | pass | pass=3 evidence_limited=0 |
| deterministic feedback vs active/verifier-like findings | evidence_limited | pass=0 evidence_limited=3 |
| no verifier vs verifier packet evidence | evidence_limited | pass=0 evidence_limited=3 |
| query_memory weak/absent vs enriched memory/tool guidance | evidence_limited | pass=0 evidence_limited=3 |
| compression/simple vs current enriched context | pass | pass=3 evidence_limited=0 |

## Cases

### filter-js-from-html

- Trace: `/Users/mohamud/Downloads/harnesseng/aether_next_build/phase2_traces/codex/filter-js-from-html.trace.json`
- Checkpoint: step `2` / turn `submit_outcome`
- Model hint present: `false`
- Prefix labels: `kernel_contract, task_prompt, envmap, objective_graph, eval_index, architect_summary, inspection_plan, proof_plan, check_plan, forbidden_paths, workflow_mode, solver_identity, refusal_boundary, selected_capabilities, action_schema`
- Structured recipe fields: `selected_capabilities, process_policy, workflow_policy, proof_plan, inspection_plan, verifier_model_tier`
- Feedback fields: `recent_progress, artifacts_present`

| metric | value |
|---|---:|
| repeated_actions_count | 0 |
| files_already_read_count | 1 |
| no_progress_streak | 1 |
| pending_checks_count | 0 |
| repair_hints_count | 0 |
| old_context_key_count | 10 |
| enriched_context_key_count | 12 |
| added_context_keys | `files_already_read, stuck` |

| axis | status | evidence / reason |
|---|---|---|
| old_context vs enriched_deterministic_context | pass | `{"added_keys": ["files_already_read", "stuck"], "enriched_context_bytes": 1436, "enriched_context_key_count": 12, "files_already_read_count": 1, "model_hint_present": false, "old_context_bytes": 1310, "old_context_key_count": 10, "repeated_actions_count": 0}` |
| preset/basic context vs context recipe/structured memory evidence | pass | `{"architect_model_tier": "default", "basic_context_labels": ["kernel_contract", "task_prompt", "envmap", "objective_graph", "eval_index", "architect_summary", "inspection_plan", "proof_plan", "check_plan", "forbidden_paths", "workflow_mode", "solver_identity", "refusal_boundary", "selected_capabilities", "action_schema"], "solver_model_tier": "default", "structured_recipe_fields": ["selected_capabilities", "process_policy", "workflow_policy", "proof_plan", "inspection_plan", "verifier_model_tier"]}` |
| deterministic feedback vs active/verifier-like findings | evidence_limited | The trace exposes deterministic feedback fields ['recent_progress', 'artifacts_present'] but no active findings or verifier packet payload field to compare against. |
| no verifier vs verifier packet evidence | evidence_limited | Only the verifier model tier is present in architect_config; the trace does not include a verifier packet or packet-level verifier evidence block. |
| query_memory weak/absent vs enriched memory/tool guidance | evidence_limited | No query_memory, memory_guidance, or similar memory-tool guidance field is present in the captured trace checkpoints. |
| compression/simple vs current enriched context | pass | `{"delta_bytes": 126, "enriched_context_bytes": 1436, "files_already_read_count": 1, "no_progress_streak": 1, "old_context_bytes": 1310, "pending_checks_count": 0, "repair_hints_count": 0, "repeated_actions_count": 0}` |

### sparql-university

- Trace: `/Users/mohamud/Downloads/harnesseng/aether_next_build/phase2_traces/codex/sparql-university.trace.json`
- Checkpoint: step `29` / turn `act`
- Model hint present: `false`
- Prefix labels: `kernel_contract, task_prompt, envmap, objective_graph, eval_index, architect_summary, inspection_plan, proof_plan, check_plan, forbidden_paths, workflow_mode, solver_identity, refusal_boundary, selected_capabilities, action_schema`
- Structured recipe fields: `selected_capabilities, process_policy, workflow_policy, proof_plan, inspection_plan, verifier_model_tier`
- Feedback fields: `artifacts_present`

| metric | value |
|---|---:|
| repeated_actions_count | 2 |
| files_already_read_count | 1 |
| no_progress_streak | 29 |
| pending_checks_count | 0 |
| repair_hints_count | 0 |
| old_context_key_count | 10 |
| enriched_context_key_count | 13 |
| added_context_keys | `files_already_read, repeated_actions, stuck` |

| axis | status | evidence / reason |
|---|---|---|
| old_context vs enriched_deterministic_context | pass | `{"added_keys": ["files_already_read", "repeated_actions", "stuck"], "enriched_context_bytes": 780, "enriched_context_key_count": 13, "files_already_read_count": 1, "model_hint_present": false, "old_context_bytes": 471, "old_context_key_count": 10, "repeated_actions_count": 2}` |
| preset/basic context vs context recipe/structured memory evidence | pass | `{"architect_model_tier": "default", "basic_context_labels": ["kernel_contract", "task_prompt", "envmap", "objective_graph", "eval_index", "architect_summary", "inspection_plan", "proof_plan", "check_plan", "forbidden_paths", "workflow_mode", "solver_identity", "refusal_boundary", "selected_capabilities", "action_schema"], "solver_model_tier": "default", "structured_recipe_fields": ["selected_capabilities", "process_policy", "workflow_policy", "proof_plan", "inspection_plan", "verifier_model_tier"]}` |
| deterministic feedback vs active/verifier-like findings | evidence_limited | The trace exposes deterministic feedback fields ['artifacts_present'] but no active findings or verifier packet payload field to compare against. |
| no verifier vs verifier packet evidence | evidence_limited | Only the verifier model tier is present in architect_config; the trace does not include a verifier packet or packet-level verifier evidence block. |
| query_memory weak/absent vs enriched memory/tool guidance | evidence_limited | No query_memory, memory_guidance, or similar memory-tool guidance field is present in the captured trace checkpoints. |
| compression/simple vs current enriched context | pass | `{"delta_bytes": 309, "enriched_context_bytes": 780, "files_already_read_count": 1, "no_progress_streak": 29, "old_context_bytes": 471, "pending_checks_count": 0, "repair_hints_count": 0, "repeated_actions_count": 2}` |

### openssl-selfsigned-cert

- Trace: `/Users/mohamud/Downloads/harnesseng/aether_next_build/phase2_traces/codex/openssl-selfsigned-cert.trace.json`
- Checkpoint: step `29` / turn `act`
- Model hint present: `false`
- Prefix labels: `kernel_contract, task_prompt, envmap, objective_graph, eval_index, architect_summary, inspection_plan, proof_plan, check_plan, forbidden_paths, workflow_mode, solver_identity, refusal_boundary, selected_capabilities, action_schema`
- Structured recipe fields: `selected_capabilities, process_policy, workflow_policy, proof_plan, inspection_plan, verifier_model_tier`
- Feedback fields: `recent_progress, artifacts_present`

| metric | value |
|---|---:|
| repeated_actions_count | 3 |
| files_already_read_count | 2 |
| no_progress_streak | 28 |
| pending_checks_count | 0 |
| repair_hints_count | 0 |
| old_context_key_count | 10 |
| enriched_context_key_count | 13 |
| added_context_keys | `files_already_read, repeated_actions, stuck` |

| axis | status | evidence / reason |
|---|---|---|
| old_context vs enriched_deterministic_context | pass | `{"added_keys": ["files_already_read", "repeated_actions", "stuck"], "enriched_context_bytes": 2366, "enriched_context_key_count": 13, "files_already_read_count": 2, "model_hint_present": false, "old_context_bytes": 1375, "old_context_key_count": 10, "repeated_actions_count": 3}` |
| preset/basic context vs context recipe/structured memory evidence | pass | `{"architect_model_tier": "default", "basic_context_labels": ["kernel_contract", "task_prompt", "envmap", "objective_graph", "eval_index", "architect_summary", "inspection_plan", "proof_plan", "check_plan", "forbidden_paths", "workflow_mode", "solver_identity", "refusal_boundary", "selected_capabilities", "action_schema"], "solver_model_tier": "default", "structured_recipe_fields": ["selected_capabilities", "process_policy", "workflow_policy", "proof_plan", "inspection_plan", "verifier_model_tier"]}` |
| deterministic feedback vs active/verifier-like findings | evidence_limited | The trace exposes deterministic feedback fields ['recent_progress', 'artifacts_present'] but no active findings or verifier packet payload field to compare against. |
| no verifier vs verifier packet evidence | evidence_limited | Only the verifier model tier is present in architect_config; the trace does not include a verifier packet or packet-level verifier evidence block. |
| query_memory weak/absent vs enriched memory/tool guidance | evidence_limited | No query_memory, memory_guidance, or similar memory-tool guidance field is present in the captured trace checkpoints. |
| compression/simple vs current enriched context | pass | `{"delta_bytes": 991, "enriched_context_bytes": 2366, "files_already_read_count": 2, "no_progress_streak": 28, "old_context_bytes": 1375, "pending_checks_count": 0, "repair_hints_count": 0, "repeated_actions_count": 3}` |

