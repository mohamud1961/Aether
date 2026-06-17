EVAL_SUPPORT_VERIFIER_BENCHMARK_CONTRACT_MAP
- wave: `failure_taxonomy/wave_02_verification_completion_and_recovery_failures`
- purpose:
  - Route verifier, grader, replay, and acceptance surfaces into separable failure-attribution layers for Wave 02.

- contract_layers:
  - layer: `inline_or_local_assertion`
    observation:
      - DeepAgents eval scaffolding uses hard success assertions (`.success`) and soft expectations (`.expect`); only success assertions fail runs.
    evidence_paths:
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/utils.py`
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/README.md`
  - layer: `benchmark_task_verifier`
    observation:
      - TerminalBench run bundles carry task-level verifier outputs (`reward.txt`, `ctrf.json`, `test-stdout.txt`) as final acceptance artifacts.
    evidence_paths:
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz`
      - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd.tar.gz`
      - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz`
  - layer: `replay_or_state_reconstruction_grader`
    observation:
      - DeepAgents external benchmark evals replay ground truth actions on fresh state and diff resulting state (`BFCL`, `tau2 airline`).
    evidence_paths:
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/external_benchmarks.py`
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/evaluation.py`
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/test_tau2_airline.py`
  - layer: `llm_judge_layer`
    observation:
      - LLM-as-judge is implemented as a success assertion over prompt criteria and is model/prompt dependent.
    evidence_paths:
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/llm_judge.py`
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/README.md`
  - layer: `reward_projection_to_observability`
    observation:
      - Harbor-to-LangSmith bridge maps missing `verifier_result`/missing reward key to fallback `0.0` reward.
    evidence_paths:
      - `research/sources/codebases/deepagents/libs/evals/deepagents_harbor/langsmith.py`

- concrete_wave_02_mismatch_examples:
  - example: `BigAI cancel-async-tasks 98b7...`
    observation:
      - Trajectory includes verifier-passed signaling, but verifier artifacts show reward `0` and one failing cancellation test.
    evidence_paths:
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
  - example: `deepagents cancel-async-tasks ca5a...`
    observation:
      - Local cleanup/concurrency checks pass in trajectory, while verifier artifacts show reward `0` and same failing edge-case test.
    evidence_paths:
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz`
  - example: `KIRA extract-moves-from-video 3df8...`
    observation:
      - Final reward is `0` with verifier similarity assertion failure despite completion claim pressure in trajectory.
    evidence_paths:
      - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
      - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd.tar.gz`
  - example: `KIRA db-wal-recovery 3481...`
    observation:
      - Final reward is `0`; exception and verifier stderr show timeout plus `getcwd`/cwd invalidation pressure.
    evidence_paths:
      - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
      - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz`

- anti_collapse_rules_for_wave_02:
  - Do not treat in-run verifier pass signals as final success without bundle verifier artifacts.
  - Do not treat benchmark readme captures as implementation proof without grader/replay code.
  - Keep `inline checks`, `verifier outputs`, `replay/state grader`, `LLM judge`, and `final reward` as separate attribution layers.
  - Keep BigAI mechanism statements labeled `behavioral reconstruction` where source is unavailable.
