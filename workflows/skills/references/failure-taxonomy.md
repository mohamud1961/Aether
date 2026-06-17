# Failure Taxonomy

Assign one primary class and zero or more contributors.

## Run Validity

- `provider_failure`
- `launch_failure`
- `environment_failure`
- `grader_failure`
- `timeout_resource_failure`
- `contamination`

Invalid classes are not model capability failures.

## Model and Harness

- `model_capability`
- `task_difficulty`
- `prompt_task_contract`
- `orientation_envcontract`
- `tool_contract_execution`
- `evidence_acquisition`
- `reduction_selection`
- `evidence_ledger`
- `no_progress_control`
- `completion_semantics`
- `verifier_prompt`
- `verifier_evidence_classifier`
- `blocker_persistence`
- `compaction_truncation`
- `service_monitoring`
- `runner_grader_isolation`
- `scheduling_resources`
- `instrumentation`

## Fake-Progress Families

- `candidate_lock_in`
- `self_authored_artifact_proof`
- `circular_same_method_check`
- `shape_or_existence_only`
- `proxy_target_success`
- `partial_sample_generalization`
- `self_authored_protocol_universe`
- `process_is_not_functionality`
- `wrong_path_success`
- `blocked_status_completion`
- `completion_ritual_pressure`
- `repeated_action_green_hunting`

## Pass Quality

- `robust`
- `weakly_verified`
- `lucky`
- `overfit`
- `unclear`

## Component Mapping Rule

Map to the component that should have changed the agent's next rational action, not merely the component closest to the final failure.

