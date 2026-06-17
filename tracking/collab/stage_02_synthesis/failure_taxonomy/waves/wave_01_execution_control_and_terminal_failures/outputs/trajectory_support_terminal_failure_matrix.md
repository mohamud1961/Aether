TRAJECTORY_SUPPORT_ARTIFACT
- artifact: trajectory_support_terminal_failure_matrix
- wave: wave_01_execution_control_and_terminal_failures
- matrix_axes:
  - rows: `system x task-family run`
  - columns:
    - execution_control_loss
    - terminal_grounding_loss
    - process_lifecycle_failure
    - timeout_or_stall_pressure
    - false_success_pressure
    - repo_state_or_control_drift
    - defended_recovery_visible
- matrix:
  - row: `deepagents / extract-moves / 67dc...`
    execution_control_loss: `yes (early cancel)`
    terminal_grounding_loss: `unknown`
    process_lifecycle_failure: `unknown`
    timeout_or_stall_pressure: `unknown`
    false_success_pressure: `no evidence`
    repo_state_or_control_drift: `no evidence`
    defended_recovery_visible: `no`
    evidence: `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
  - row: `deepagents / cancel-async / ca5a...`
    execution_control_loss: `no`
    terminal_grounding_loss: `no`
    process_lifecycle_failure: `mitigated`
    timeout_or_stall_pressure: `no`
    false_success_pressure: `low`
    repo_state_or_control_drift: `no`
    defended_recovery_visible: `yes`
    evidence: `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - row: `deepagents / db-wal / 0333...`
    execution_control_loss: `no`
    terminal_grounding_loss: `no`
    process_lifecycle_failure: `low`
    timeout_or_stall_pressure: `no`
    false_success_pressure: `low`
    repo_state_or_control_drift: `managed (checkpoint side-effect acknowledged)`
    defended_recovery_visible: `yes`
    evidence: `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
  - row: `terminus-kira / extract-moves / 3df8...`
    execution_control_loss: `partial (OCR interruption)`
    terminal_grounding_loss: `partial`
    process_lifecycle_failure: `possible`
    timeout_or_stall_pressure: `possible`
    false_success_pressure: `high`
    repo_state_or_control_drift: `low`
    defended_recovery_visible: `no`
    evidence: `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
  - row: `terminus-kira / cancel-async / 8d55...`
    execution_control_loss: `no`
    terminal_grounding_loss: `no`
    process_lifecycle_failure: `yes before repair`
    timeout_or_stall_pressure: `no`
    false_success_pressure: `medium (early pseudo-pass)`
    repo_state_or_control_drift: `low`
    defended_recovery_visible: `yes (after retest)`
    evidence: `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - row: `terminus-kira / db-wal / 3481...`
    execution_control_loss: `yes`
    terminal_grounding_loss: `high`
    process_lifecycle_failure: `high`
    timeout_or_stall_pressure: `possible`
    false_success_pressure: `medium`
    repo_state_or_control_drift: `high`
    defended_recovery_visible: `no`
    evidence: `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  - row: `BigAI / extract-moves / 953d...`
    execution_control_loss: `no (active supervision)`
    terminal_grounding_loss: `unclear`
    process_lifecycle_failure: `managed via wait/kill loop`
    timeout_or_stall_pressure: `possible`
    false_success_pressure: `unknown (closure missing)`
    repo_state_or_control_drift: `unknown`
    defended_recovery_visible: `unknown`
    evidence: `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
  - row: `BigAI / cancel-async / 17f3...`
    execution_control_loss: `low`
    terminal_grounding_loss: `low`
    process_lifecycle_failure: `mitigated`
    timeout_or_stall_pressure: `low`
    false_success_pressure: `reduced by verifier`
    repo_state_or_control_drift: `controlled`
    defended_recovery_visible: `yes`
    evidence: `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
  - row: `BigAI / cancel-async / d799...`
    execution_control_loss: `low`
    terminal_grounding_loss: `low`
    process_lifecycle_failure: `mitigated`
    timeout_or_stall_pressure: `low`
    false_success_pressure: `reduced by verifier + cleanliness gate`
    repo_state_or_control_drift: `controlled after cleanup`
    defended_recovery_visible: `yes`
    evidence: `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
  - row: `BigAI / db-wal / a1ed..., e150..., 47f2...`
    execution_control_loss: `low`
    terminal_grounding_loss: `low`
    process_lifecycle_failure: `mitigated`
    timeout_or_stall_pressure: `low`
    false_success_pressure: `reduced by verifier`
    repo_state_or_control_drift: `managed through backup/restore discipline`
    defended_recovery_visible: `yes`
    evidence:
      - `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`
      - `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
      - `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`
- matrix_notes:
  - BigAI rows remain `behavioral reconstruction`.
  - `timeout_or_stall_pressure` is supplemented by cluster-level evidence in `research/analysis/bigai_trace_layer/output/answered_questions.md`.
