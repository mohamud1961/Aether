EVAL_BENCHMARK_DOSSIER
- dossier_type: wave-specific eval benchmark dossier
- target: verification_completion_recovery_failures
- status: wave_02_informal_followup_01_updated_2026_04_10

- source_scope:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_issues_postmortems_analyst__followup_01.md`
  - `tracking/collab/stage_02_synthesis/eval_benchmark_dossiers/verification_completion_and_recovery.md`
  - [private-source: issue/src_iss_5d861db09829]
  - [private-source: issue/src_iss_6ba217fff208]
  - [private-source: issue/src_iss_613424e145e5]
  - [private-source: issue/src_iss_edac72dd9b31]
  - [private-source: issue/src_iss_222a58240294]
  - [private-source: issue/src_iss_4c8fe1b50b87]
  - [private-source: issue/src_iss_da41417f5655]
  - [private-source: issue/src_iss_ed4eb57a9d2b]
  - [private-source: issue/src_iss_a1a5a26e92ab]
  - [private-source: issue/src_iss_f44f83f3fbc3]
  - [private-source: issue/src_iss_f07284ab370e]
  - [private-source: informal/cursor_cursorbench.md]
  - [private-source: informal/openai_evmbench.md]
  - [private-source: informal/langchain_agent_observability.md]

- contract_or_logic:
  - This update records informal/issue pressure that should shape eval-lane probe design.
  - It does not promote issue-derived claims as source-backed grader or replay implementation facts.

- failure_modes_supported:
  - `completion_signal_without_outcome_proof`
    - signal:
      - completion can be emitted despite missing target-side confirmation.
    - confidence: medium
    - evidence:
      - [private-source: issue/src_iss_5d861db09829]
      - [private-source: issue/src_iss_6ba217fff208]

  - `resume_contract_state_integrity_break`
    - signal:
      - stale indexes/checkpoints and transcript-shape failures can invalidate resume even when logs exist.
    - confidence: high
    - evidence:
      - [private-source: issue/src_iss_613424e145e5]
      - [private-source: issue/src_iss_edac72dd9b31]
      - [private-source: issue/src_iss_222a58240294]

  - `crash_non_terminalization`
    - signal:
      - crash recovery can strand runs in non-terminal states that block new execution.
    - confidence: high
    - evidence:
      - [private-source: issue/src_iss_4c8fe1b50b87]
      - [private-source: issue/src_iss_da41417f5655]
      - [private-source: issue/src_iss_ed4eb57a9d2b]

  - `restore_rewind_secondary_regression`
    - signal:
      - restore/rewind features can introduce correctness and security regressions.
    - confidence: medium
    - evidence:
      - [private-source: issue/src_iss_a1a5a26e92ab]
      - [private-source: issue/src_iss_f44f83f3fbc3]

  - `opaque_error_surface_blocks_recovery_policy`
    - signal:
      - unstructured errors reduce the agent/harness ability to choose correct recovery branches.
    - confidence: medium
    - evidence:
      - [private-source: issue/src_iss_f07284ab370e]
      - [private-source: issue/src_iss_d3818cf54a20]

- informal_pressure_on_eval_design:
  - required_probe: `completion_claim_vs_verified_outcome`
    rationale:
      - detect divergence between local completion narration and externally verified success.
  - required_probe: `resume_state_integrity`
    rationale:
      - stress stale-index, stale-checkpoint, and oversized transcript cases.
  - required_probe: `crash_terminalization`
    rationale:
      - verify interrupted sessions are reconciled into explicit terminal states before further turns.
  - required_probe: `error_contract_shape`
    rationale:
      - compare recovery outcomes under plain-text errors vs typed recoverability metadata.

- local_eval_links:
  - `evals/verification_eval.py`
  - `runner/evaluator.py`

- contradictions:
  - benchmark and quality narratives emphasize measurable progress, while issue evidence shows production completion/recovery failures that can evade narrow success metrics.
  - long-horizon autonomy claims coexist with recurring resume-state and terminalization failures.

- carry_forward_cautions:
  - keep verifier/grader/replay/final-acceptance layers explicitly separate.
  - avoid treating issue pressure as direct proof of benchmark-contract root cause.
  - preserve mixed-cause attribution unless trajectory/codebase/eval evidence isolates cause.

- confidence_notes:
  - high confidence:
    - existence of evaluation pressure families around completion/recovery mismatch.
  - medium confidence:
    - mapping from these reports to specific grader/replay root causes without direct implementation reads.

- next_eval_lane_requests:
  - Add explicit mismatch counters for `{inline completion signal, verifier output, replay/grader result, final acceptance}`.
  - Add restart and crash-recovery probes for non-terminal stuck state.
  - Add resume robustness probes for stale index and oversized transcript history.
  - Add structured error contract A/B probes for recovery success rates.
