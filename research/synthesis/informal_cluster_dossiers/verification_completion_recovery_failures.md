INFORMAL_CLUSTER_DOSSIER
- cluster_topic: verification_completion_recovery_failures
- status: wave_02_informal_followup_01_updated_2026_04_10
- scope:
  - Contradiction-pressure routing for verification/completion/recovery failures.
  - Informal/issues/postmortems are pressure evidence only; direct trajectory/source/eval evidence outranks these clusters.

- coverage_used:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_issues_postmortems_analyst__followup_01.md`
  - `research/sources/issues/src_iss_5d861db09829/artifact.txt`
  - `research/sources/issues/src_iss_6ba217fff208/artifact.txt`
  - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
  - `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`
  - `research/sources/issues/src_iss_222a58240294/artifact.txt`
  - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
  - `research/sources/issues/src_iss_da41417f5655/artifact.txt`
  - `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt`
  - `research/sources/issues/src_iss_a1a5a26e92ab/artifact.txt`
  - `research/sources/issues/src_iss_a1b2c3d4e5f6/artifact.txt`
  - `research/sources/issues/src_iss_b5d3d874490a/artifact.txt`
  - `research/sources/issues/src_iss_f44f83f3fbc3/artifact.txt`
  - `research/sources/issues/src_iss_f07284ab370e/artifact.txt`
  - `research/sources/issues/src_iss_31cf9134cefa/artifact.txt`
  - `research/sources/postmortems/src_pmt_ca79e818d699/artifact.txt`
  - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`
  - `research/sources/postmortems/src_pmt_2c716b81f9a5/artifact.txt`
  - `research/sources/postmortems/src_pmt_afc13590bd50/artifact.txt`
  - `research/sources/informal/cursor_long_running_agents.md`
  - `research/sources/informal/anthropic_long_running_harness.md`
  - `research/sources/informal/cursor_dynamic_context_discovery.md`
  - `research/sources/informal/langchain_autonomous_context.md`
  - `research/sources/informal/langchain_anatomy_of_harness.md`

- coverage_not_yet_used:
  - `research/sources/issues/src_iss_*.txt` not listed above.
  - `research/sources/informal/x_*.md` social captures.
  - direct trajectory and benchmark implementation surfaces (handled by other lanes).

- pressure_clusters:
  - cluster: false_completion_without_target_side_proof
    observation:
      - completion status can be asserted before target-side behavior is proven.
    inference:
      - completion policy weakness and verifier omission are active contributors.
    confidence: medium
    evidence_paths:
      - `research/sources/issues/src_iss_5d861db09829/artifact.txt`
      - `research/sources/issues/src_iss_6ba217fff208/artifact.txt`
      - `research/sources/postmortems/src_pmt_ca79e818d699/artifact.txt`

  - cluster: resume_index_and_transcript_integrity_drift
    observation:
      - stale/missing index metadata and oversized transcript lines can render resume unusable despite preserved logs.
    inference:
      - recovery is sensitive to storage/index contracts and transcript compaction design.
    confidence: high
    evidence_paths:
      - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
      - `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`
      - `research/sources/issues/src_iss_222a58240294/artifact.txt`
      - `research/sources/issues/src_iss_a1b2c3d4e5f6/artifact.txt`

  - cluster: crash_recovery_non_terminal_limbo
    observation:
      - crash scenarios can leave sessions in non-terminal running/thinking states that block continuation.
    inference:
      - explicit terminalization on recovery is a distinct reliability requirement.
    confidence: high
    evidence_paths:
      - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
      - `research/sources/issues/src_iss_da41417f5655/artifact.txt`
      - `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt`

  - cluster: rewind_restore_secondary_failure_surface
    observation:
      - rewind/restore logic can introduce new correctness/security failures (state nullification, weak restore-path assurances, unsafe deserialization concerns).
    inference:
      - recovery systems must be treated as first-class failure surfaces, not only mitigation paths.
    confidence: medium
    evidence_paths:
      - `research/sources/issues/src_iss_a1a5a26e92ab/artifact.txt`
      - `research/sources/issues/src_iss_b5d3d874490a/artifact.txt`
      - `research/sources/issues/src_iss_f44f83f3fbc3/artifact.txt`

  - cluster: opaque_error_contracts_degrade_recovery
    observation:
      - unstructured error responses leave recoverability ambiguous and increase retry thrash risk.
    inference:
      - structured error type + recoverability hints are a likely recovery stabilizer.
    confidence: medium
    evidence_paths:
      - `research/sources/issues/src_iss_f07284ab370e/artifact.txt`
      - `research/sources/issues/src_iss_d3818cf54a20/artifact.txt`
      - `research/sources/issues/src_iss_31cf9134cefa/artifact.txt`
      - `research/sources/informal/langchain_anatomy_of_harness.md`

- contradictions:
  - reliability-forward product narratives for long-running autonomous execution coexist with repeated production incident reports on resume drift and stuck-state recovery.
  - context-management guidance claims stronger long-horizon continuity, while issue reports show concrete transcript/index fragility.

- carry_forward_cautions:
  - do not collapse completion, verifier, grader/replay, and recovery layers.
  - treat mixed-cause attribution as default unless direct evidence isolates cause.
  - retain low-credibility handling: empty capture (`src_pmt_2c716b81f9a5`) and ad-heavy mixed capture (`src_pmt_afc13590bd50`) are non-promotable.

- downstream_relevance:
  - failure_taxonomy:
    - strengthens candidate subfamilies: false completion, resume/index drift, crash non-terminalization, restore-path secondary failures.
  - eval_implications:
    - motivates explicit mismatch probes across completion signal vs verifier/grader/final acceptance.
