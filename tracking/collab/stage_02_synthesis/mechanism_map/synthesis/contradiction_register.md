# Mechanism Map Contradiction Register

Date: 2026-04-04

- contradiction_id: bigai_behavior_without_source
  - summary: BigAI planner or executor or verifier separation is strongly supported by trajectories and local trace reconstruction, but there is no mirrored source to confirm implementation details.
  - status: open
  - related_paths:
    - `/Users/mohamud/Downloads/harnesseng/research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
    - `/Users/mohamud/Downloads/harnesseng/research/sources/trajectories/BigAI/`

- contradiction_id: deepagents_sandbox_surface_vs_backend_reality
  - summary: DeepAgents surface language and docs imply sandbox discipline, while mirrored source includes an unsandboxed `LocalShellBackend`.
  - status: open
  - related_paths:
    - `/Users/mohamud/Downloads/harnesseng/research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/filesystem.py`
    - `/Users/mohamud/Downloads/harnesseng/research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/local_shell.py`

- contradiction_id: internal_verifier_status_vs_external_grader_outcome
  - summary: Internal verifier events can show success while the external grader still returns failure.
  - status: open
  - related_paths:
    - `/Users/mohamud/Downloads/harnesseng/research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
    - `/Users/mohamud/Downloads/harnesseng/research/sources/codebases/deepagents/libs/evals/tests/evals/external_benchmarks.py`

- contradiction_id: kira_visible_verifier_weakness_vs_trace_rendering
  - summary: KIRA looks less explicitly verifier-structured than BigAI in the sampled traces, but it is unclear how much of that is real harness difference versus trace-style or visibility difference.
  - status: open
  - related_paths:
    - `/Users/mohamud/Downloads/harnesseng/research/sources/trajectories/terminus-kira/`
    - `/Users/mohamud/Downloads/harnesseng/research/sources/codebases/KIRA/`

- contradiction_id: formal_intent_vs_formal_content_access
  - summary: The formal lane has strong doc-backed mechanism intent, but actual paper-content coverage is still weak because PDFs are not yet text-accessible.
  - status: open
  - related_paths:
    - `/Users/mohamud/Downloads/harnesseng/research/sources/papers/`
    - `/Users/mohamud/Downloads/harnesseng/research/sources/papers/papers_text/`

- contradiction_id: context_and_output_offload_claims_without_enough_behavioral_confirmation
  - summary: Informal and source lanes both point to file-backed context and output offload as important, but Wave 01 does not yet show enough direct trajectory evidence to promote that family confidently.
  - status: open
  - related_paths:
    - `/Users/mohamud/Downloads/harnesseng/research/sources/informal/cursor_dynamic_context_discovery.md`
    - `/Users/mohamud/Downloads/harnesseng/research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/summarization.py`

- contradiction_id: wave_01_anchor_value_vs_artifact_completion
  - summary: Wave 01 produced real and reusable mechanism anchors, but major unread path families mean it must be preserved as an exploratory anchor rather than treated as artifact completion.
  - status: resolved_for_now_by_governance
  - related_paths:
    - `/Users/mohamud/Downloads/harnesseng/tracking/collab/stage_02_synthesis/deep_synthesis_wave_plan/synthesis/principal_synthesis.md`
    - `/Users/mohamud/Downloads/harnesseng/tracking/collab/stage_02_synthesis/mechanism_map/synthesis/principal_synthesis.md`
