SYNTHESIS_PREP_OUTPUT
- artifact: `evidence_inventory`
- scope:
  - This is a bounded repair pass on the same Stage 2A artifact. It repairs `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` against `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/red_team.md` and `tracking/collab/stage_02_synthesis/evidence_inventory/synthesis/principal_synthesis.md`; it does not open `mechanism_map` or `failure_taxonomy`.
  - First-wave evidence-bearing synthesis remains anchored on `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`: 247 captured source IDs out of 288 accepted IDs, with the remaining 41 held in `research/intake/rejected/2026-04-01__accepted_blocked_exceptions.json` as metadata-only blocked exceptions.
  - The full frozen repo-local corpus still extends beyond the intake layer and must be routed explicitly: `research/sources/trajectories/` (3 families x 89 task directories), `research/sources/informal/` (102 markdown notes), `research/sources/postmortems/` (6 captured retrospectives), mirrored code/eval repos under `research/sources/codebases/{deepagents,KIRA,a-evolve,langchain,quarantine}`, 9 captured standalone `src_cod_*` assets, 5 captured benchmark assets under `research/sources/benchmarks/`, local analysis under `research/analysis/`, and local target harness code in `blocks/`, `runner/`, and `evals/`.
  - Deep synthesis is still blocked until the repaired organizer survives one rerun of the targeted synthesis-prep red-team review.
- evidence_inventory_paths:
  - Corpus boundary and routing authority:
    - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
    - `research/intake/normalized/manifests/corpus__deduped.json`
    - `research/intake/rejected/2026-04-01__accepted_blocked_exceptions.json`
    - `research/intake/normalized/qc/2026-04-01__qc_report.json`
    - `research/intake/records/`
    - `research/intake/normalized/manifests/*__accepted.json`
  - Repair governance:
    - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/red_team.md`
    - `tracking/collab/stage_02_synthesis/evidence_inventory/synthesis/principal_synthesis.md`
    - `tracking/collab/stage_02_synthesis/red_team_review/outputs/red_team_review_adjudicated.md`
  - Direct behavior evidence:
    - `research/sources/trajectories/BigAI/`
    - `research/sources/trajectories/deepagents/`
    - `research/sources/trajectories/terminus-kira/`
    - `research/analysis/bigai_trace_layer/output/corpus_summary.json`
    - `research/analysis/bigai_trace_layer/output/task_index.json`
    - `research/analysis/bigai_trace_layer/output/question_answers.json`
    - `research/analysis/bigai_trace_layer/output/exemplar_runs.json`
    - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
    - `research/analysis/bigai_trace_layer/output/coverage_report.json`
  - Implementation and eval evidence:
    - `research/sources/codebases/deepagents/libs/deepagents/`
    - `research/sources/codebases/deepagents/libs/evals/`
    - `research/sources/codebases/KIRA/terminus_kira/`
    - `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt`
    - `research/sources/codebases/a-evolve/agent_evolve/benchmarks/`
    - `research/sources/codebases/a-evolve/seed_workspaces/`
    - `research/sources/codebases/langchain/agentevals/`
    - `research/sources/codebases/langchain/openevals/`
    - `research/sources/codebases/quarantine/claw-code/`
    - `research/sources/codebases/src_cod_*/capture.json`
    - `research/sources/benchmarks/src_bnm_*/capture.json`
    - `blocks/`
    - `runner/`
    - `evals/`
  - Conceptual, retrospective, and contradiction evidence:
    - `research/sources/papers/`
    - `research/sources/docs/`
    - `research/sources/issues/`
    - `research/sources/postmortems/`
    - `research/sources/informal/`
    - `research/analysis/lego_dimensions.md`
    - `research/analysis/patterns.md`
    - `research/analysis/failure_modes.md`
    - `tracking/ledger/open_questions.md`
    - `SYNTHESIS_PREP_CHECKLIST.md`
    - `MECHANISM_CARD_SCHEMA.md`
    - `FAILURE_CARD_SCHEMA.md`
    - `TRAJECTORY_SOURCE_CASE_STUDY_TEMPLATE.md`
- trajectory_priority_list:
  - Priority 1 terminal-control and process-control set: `headless-terminal`, `cancel-async-tasks`, and `db-wal-recovery`. These are the cleanest first-wave tasks for terminal control, process cleanup, stateful recovery, and verifier discipline across all three families.
  - Priority 2 failure-heavy set: `extract-moves-from-video` and `gpt2-codegolf`. These force the organizer to support failure extraction instead of only comparison-friendly success cases.
  - Priority 3 branching and repo-state set: `break-filter-js-from-html` and `git-multibranch`. These expose executor coordination, cleanup, and repository-state management.
  - Priority 4 gap and malformed-evidence set: `install-windows-3.11`, `gcode-to-text`, `qemu-startup`, `git-leak-recovery`, and `prove-plus-comm` as explicit artifact-gap notes rather than silent omissions.
- codebase_priority_list:
  - Priority 1 visible terminal harness implementations: `research/sources/codebases/deepagents/libs/deepagents/`, `research/sources/codebases/KIRA/terminus_kira/`, `research/sources/codebases/quarantine/claw-code/`, `research/sources/codebases/src_cod_ad409dc1ebde/`, and `research/sources/codebases/src_cod_564b05dcc95b/`.
  - Priority 1 eval and replay infrastructure: `research/sources/codebases/deepagents/libs/evals/`, `research/sources/codebases/langchain/agentevals/`, `research/sources/codebases/langchain/openevals/`, and `research/sources/codebases/src_cod_e231561a3d69/`.
  - Priority 2 state/tool-gateway and security captures: `research/sources/codebases/src_cod_086db5a6312e/`, `research/sources/codebases/src_cod_c7b08f87aeac/`, and `research/sources/codebases/src_cod_a1e1a27e13a1/`.
  - Priority 3 narrow prompt/skill/changelog captures: `research/sources/codebases/src_cod_18ba360eb4b2/`, `research/sources/codebases/src_cod_87b73c75d11a/`, and `research/sources/codebases/src_cod_c717c148e387/`.
  - Priority 4 local target harness code: `blocks/`, `runner/`, and `evals/` for gap analysis only.
- eval_repo_priority_list:
  - Priority 1: `research/sources/codebases/deepagents/libs/evals/` because it joins Harbor wrappers, benchmark adapters, eval categories, failure reporting, and LangSmith trace handling in a terminal-agent setting.
  - Priority 1: `research/sources/codebases/src_cod_e231561a3d69/` because standardized trajectories and deterministic replay directly connect evaluation rigor to trajectory evidence.
  - Priority 2: `research/sources/codebases/langchain/agentevals/` for trajectory match and trajectory LLM-as-judge patterns.
  - Priority 2: `research/sources/codebases/langchain/openevals/` for general judge, code, multimodal, and tool-call grading primitives.
  - Priority 3: `research/sources/codebases/a-evolve/agent_evolve/benchmarks/` plus the five `src_bnm_*` captures for benchmark contracts, graders, and anti-cheat structure.
  - Priority 4: local `evals/` and `runner/evaluator.py` only as low-confidence target-state placeholders.
- lego_dimension_map:

| Dimension | Direct behavior evidence | Implementation / eval evidence | Supporting conceptual evidence | First repair use |
| --- | --- | --- | --- | --- |
| `Orientation` | `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`; `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt` | `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt`; `research/sources/codebases/deepagents/libs/deepagents/deepagents/base_prompt.md`; `research/sources/codebases/src_cod_87b73c75d11a/capture.json` | `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt` | Anchor how systems frame autonomy, plan-first behavior, and initial task decomposition before tool use begins. |
| `Tool Surface` | `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`; `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt` | `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`; `research/sources/codebases/src_cod_086db5a6312e/capture.json`; `research/sources/codebases/src_cod_c7b08f87aeac/capture.json`; `research/sources/codebases/src_cod_ad409dc1ebde/capture.json` | `research/sources/postmortems/src_pmt_350e236460b0/artifact.txt`; `research/sources/informal/cursor_dynamic_context_discovery.md` | Map which systems expose shell/file/image/MCP/security controls directly versus through gateways or discovery layers. |
| `Execution Loop` | `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`; `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`; `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt` | `research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py`; `research/sources/codebases/src_cod_564b05dcc95b/capture.json`; `research/sources/codebases/a-evolve/agent_evolve/benchmarks/base.py` | `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`; `research/sources/informal/cursor_long_running_agents.md` | Separate planner/executor/verifier, loop, and long-running-review patterns before any mechanism cards are drafted. |
| `Context Strategy` | `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`; `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt` | `research/sources/codebases/deepagents/libs/deepagents/deepagents/base_prompt.md`; `research/sources/codebases/src_cod_086db5a6312e/capture.json`; `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py` | `research/sources/postmortems/src_pmt_350e236460b0/artifact.txt`; `research/sources/informal/humanlayer_12_factor_agents.md` | Bind file-backed context retrieval, summarization, externalized state, and deterministic prefetch into one usable comparison lane. |
| `Verification` | `research/sources/trajectories/BigAI/adaptive-rejection-sampler/c05344ea-9a06-490d-9310-937670fb7b4a.tar.gz`; `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt` | `research/sources/codebases/deepagents/libs/evals/`; `research/sources/codebases/src_cod_e231561a3d69/capture.json`; `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`; `research/sources/codebases/src_cod_18ba360eb4b2/capture.json` | `research/sources/benchmarks/src_bnm_8c3b5dc456f5/capture.json`; `research/sources/benchmarks/src_bnm_e5f985948a0e/capture.json`; `research/sources/postmortems/src_pmt_ca79e818d699/artifact.txt` | Index explicit verifier loops, replay, double-confirm completion, judge infrastructure, and anti-cheat benchmark logic. |
| `Error Recovery` | `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`; `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`; `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt` | `research/sources/codebases/src_cod_564b05dcc95b/capture.json`; `research/sources/codebases/a-evolve/seed_workspaces/`; `research/sources/codebases/src_cod_a1e1a27e13a1/capture.json`; `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py` | `research/analysis/bigai_trace_layer/output/exemplar_runs.json`; `tracking/ledger/open_questions.md` | Keep rollback, isolation, retry, and process-cleanup behavior visible before any failure taxonomy is opened. |

- trajectory_matrix:
  - This is a first-wave run-level matrix for the prioritized case slate. It is intentionally selective rather than a 267-run dump, but every row is grounded in a concrete run or bundle on disk.

| Task | System family | Run ID | Artifacts | Failure tag | Verification tag | Recovery tag | Context / control tag | Why first-wave |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `headless-terminal` | `BigAI` | `cec71502-c287-4257-9aba-4e33b3668881` | `traj+tar` | `low in BigAI task index` | `explicit-verifier-likely` | `low` | `terminal-control` | Clean terminal-control reference run. |
| `headless-terminal` | `deepagents` | `8359bd4b-bdf5-4c33-b511-869e048e9f6f` | `traj+tar` | `comparison-run` | `inspect` | `low` | `terminal-control` | Compare visible harness behavior on the same terminal task. |
| `headless-terminal` | `terminus-kira` | `a2ae3f53-cc59-4049-87ca-9e23781c00e4` | `traj+tar` | `comparison-run` | `inspect` | `low` | `terminal-control` | Terminal-native tool surface plus visible prompt/tool schema. |
| `cancel-async-tasks` | `BigAI` | `17f3a357-c55a-4171-af6a-510581362baa` | `traj+tar` | `moderate in BigAI task index` | `explicit-verifier-likely` | `process-cleanup` | `terminal-process-control` | Recovery/process-control case with some failure signal. |
| `cancel-async-tasks` | `deepagents` | `ca5a6b83-cd19-46da-8a12-1070b4f476bf` | `traj+tar` | `comparison-run` | `inspect` | `process-cleanup` | `terminal-process-control` | Compare process control without relying only on BigAI. |
| `cancel-async-tasks` | `terminus-kira` | `8d55545f-8ce2-49b7-9fc1-231635fc6a2d` | `traj+tar` | `comparison-run` | `inspect` | `process-cleanup` | `terminal-process-control` | Pairs visible terminal harness code with a recovery-sensitive task. |
| `db-wal-recovery` | `BigAI` | `47f2454e-2528-4427-94c8-6b13f8c63f53` | `traj+tar` | `low in BigAI task index` | `explicit verifier` | `safety-backup` | `stateful workspace` | Best stateful recovery exemplar already named in BigAI analysis. |
| `db-wal-recovery` | `deepagents` | `0333a30b-2678-4f0e-a672-26279fd01b7a` | `traj+tar` | `comparison-run` | `inspect` | `stateful recovery` | `stateful workspace` | Cross-family comparison on the strongest recovery task. |
| `db-wal-recovery` | `terminus-kira` | `3481ab1c-d322-4bda-bd10-49c0708403d2` | `traj+tar` | `comparison-run` | `inspect` | `stateful recovery` | `stateful workspace` | Connects KIRA completion checks to a recovery-heavy workload. |
| `extract-moves-from-video` | `BigAI` | `953d42f6-a999-4f95-bc53-79cc2952688d` | `traj+tar` | `high in BigAI task index` | `failed-or-weak` | `weak` | `media-plus-tool context` | Failure-heavy multimodal case for the next failure lane. |
| `extract-moves-from-video` | `deepagents` | `67dc6598-86d3-4439-b6be-de398cd964e8` | `traj+tar` | `comparison-run` | `inspect` | `unknown` | `media-plus-tool context` | Needed so failure analysis is not BigAI-only. |
| `extract-moves-from-video` | `terminus-kira` | `3df89e49-6187-4805-a273-641b4d82c5cd` | `traj+tar` | `comparison-run` | `inspect` | `unknown` | `media-plus-tool context` | Same failure-heavy task with KIRA’s multimodal tool surface nearby. |
| `gpt2-codegolf` | `BigAI` | `170986fa-f818-4d0f-9bbd-21f495f4ad9f` | `traj+tar` | `very high in BigAI task index` | `insufficient` | `weak` | `long-horizon coding control` | Clear BigAI failure cluster that the earlier organizer underweighted. |
| `gpt2-codegolf` | `deepagents` | `2886c1b1-248c-4f61-ae08-020f2b466065` | `traj+tar` | `comparison-run` | `inspect` | `unknown` | `long-horizon coding control` | Keeps the failure-heavy slate cross-family. |
| `gpt2-codegolf` | `terminus-kira` | `0b44fad6-7d6b-44a5-a9df-9f2bdeaf68bf` | `tar only` | `artifact-gap` | `unknown` | `unknown` | `long-horizon coding control` | Explicit example of a family/task gap that should remain visible in case selection. |
| `break-filter-js-from-html` | `BigAI` | `4e6a3070-4a78-4c1a-ac1c-c0651045db08` | `traj+tar` | `low in BigAI task index` | `explicit verifier` | `executor handoff` | `branching / coordination` | Rare explicit executor-to-executor ask. |
| `break-filter-js-from-html` | `deepagents` | `802e3807-8f1a-4c15-991c-9cdb03d16cef` | `traj+tar` | `comparison-run` | `inspect` | `cleanup` | `branching / coordination` | Compare coordination behavior against visible code. |
| `break-filter-js-from-html` | `terminus-kira` | `eaf5da17-d140-4652-bd00-3e6a83bf66cf` | `traj+tar` | `comparison-run` | `inspect` | `cleanup` | `branching / coordination` | Same branch-sensitive task with KIRA’s tool contract. |
| `git-multibranch` | `BigAI` | `62d2bdf3-6678-44a2-bb90-efd397b7937d` | `traj+tar` | `low in BigAI task index` | `explicit verifier-likely` | `merge / cleanup` | `repo-state control` | Strong repo-state and cleanup comparison task. |
| `git-multibranch` | `deepagents` | `e6e6d3a5-ee75-489a-a4a0-c3a751ea3421` | `traj+tar` | `comparison-run` | `inspect` | `merge / cleanup` | `repo-state control` | Visible source plus trajectory on a repo-state-sensitive task. |
| `git-multibranch` | `terminus-kira` | `80b5619c-2b60-45e3-b209-ffbf02d27aa9` | `traj+tar` | `comparison-run` | `inspect` | `merge / cleanup` | `repo-state control` | Cross-family control case with visible terminal harness code. |

- codebase_eval_matrix:

| Asset | Type | Relevant subsystem / files | Lane | Confidence | Triage |
| --- | --- | --- | --- | --- | --- |
| `research/sources/codebases/deepagents/libs/deepagents/` | mirrored repo | `deepagents/base_prompt.md`, `deepagents/graph.py` | `mechanism` | `high` | `first-wave` |
| `research/sources/codebases/deepagents/libs/evals/` | mirrored repo | `deepagents_harbor/deepagents_wrapper.py`, `tests/evals/*`, `deepagents_evals/categories.json` | `both` | `high` | `first-wave` |
| `research/sources/codebases/KIRA/terminus_kira/` | mirrored repo | `terminus_kira.py` | `both` | `high` | `first-wave` |
| `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt` | mirrored prompt | terminal system prompt and completion rules | `mechanism` | `high` | `first-wave` |
| `research/sources/codebases/quarantine/claw-code/` | mirrored repo | Claude Code exact Python source | `mechanism` | `high` | `first-wave` |
| `research/sources/codebases/a-evolve/agent_evolve/benchmarks/` | mirrored repo | `benchmarks/base.py`, adapters | `both` | `medium-high` | `second-wave` |
| `research/sources/codebases/a-evolve/seed_workspaces/` | mirrored repo | workspace contracts and manifests | `mechanism` | `medium-high` | `second-wave` |
| `research/sources/codebases/langchain/agentevals/` | mirrored repo | trajectory match and LLM-as-judge utilities | `eval` | `high` | `second-wave` |
| `research/sources/codebases/langchain/openevals/` | mirrored repo | judge primitives for code, multimodal, tool calls | `eval` | `high` | `second-wave` |
| `research/sources/codebases/src_cod_086db5a6312e/capture.json` | standalone code capture | OpenHands V1 state management and tool gateways (`artifact.zip`) | `mechanism` | `medium-high` | `first-wave standalone` |
| `research/sources/codebases/src_cod_18ba360eb4b2/capture.json` | standalone code capture | code-change-verification skill capture (`artifact.zip`) | `verification` | `medium` | `supporting` |
| `research/sources/codebases/src_cod_564b05dcc95b/capture.json` | standalone code capture | RALPH Loop continuous coding framework (`artifact.zip`) | `both` | `medium-high` | `first-wave standalone` |
| `research/sources/codebases/src_cod_87b73c75d11a/capture.json` | standalone code capture | Codex CLI system prompt capture (`artifact.zip`) | `mechanism` | `medium` | `supporting` |
| `research/sources/codebases/src_cod_a1e1a27e13a1/capture.json` | standalone code capture | migration / agent portability framework (`artifact.zip`) | `recovery` | `medium` | `second-wave standalone` |
| `research/sources/codebases/src_cod_ad409dc1ebde/capture.json` | standalone code capture | Aider terminal baseline (`artifact.zip`) | `mechanism` | `medium-high` | `first-wave comparison` |
| `research/sources/codebases/src_cod_c717c148e387/capture.json` | standalone code capture | Claude Code changelog snapshot (`artifact.zip`) | `conceptual` | `low-medium` | `demote unless contradicted elsewhere` |
| `research/sources/codebases/src_cod_c7b08f87aeac/capture.json` | standalone code capture | agentsh execution-layer security (`artifact.zip`) | `mechanism` | `medium` | `second-wave standalone` |
| `research/sources/codebases/src_cod_e231561a3d69/capture.json` | standalone code capture | SWE-agent standardized trajectories and deterministic replay (`artifact.zip`) | `both` | `medium-high` | `first-wave standalone` |
| `research/sources/benchmarks/src_bnm_8c3b5dc456f5/capture.json` | benchmark capture | ImpossibleBench anti-cheat contract | `eval` | `medium-high` | `first-wave benchmark` |
| `research/sources/benchmarks/src_bnm_e1cfa2bf78c9/capture.json` | benchmark capture | WebArena-Infinity browser verification API | `eval` | `medium` | `second-wave benchmark` |
| `research/sources/benchmarks/src_bnm_e5f985948a0e/capture.json` | benchmark capture | SWE-bench Verified and automation | `eval` | `medium-high` | `first-wave benchmark` |
| `research/sources/benchmarks/src_bnm_f6e5d4c3b2a1/capture.json` | benchmark capture | SlopCodeBench iterative degradation signal | `eval` | `medium-high` | `first-wave benchmark` |
| `research/sources/benchmarks/src_bnm_facefeed2020/capture.json` | benchmark capture | NIKA network sabotage arena | `eval` | `medium` | `second-wave benchmark` |
| `blocks/`, `runner/`, `evals/` | local target code | swappable blocks, agent loop stubs, placeholder evals | `target-state` | `low` | `gap-analysis only` |

- benchmark_inventory:

| Capture | Focus | What it teaches | Confidence | Use |
| --- | --- | --- | --- | --- |
| `src_bnm_8c3b5dc456f5` | anti-cheat / specification gaming | benchmark-level honesty pressure, cheating resistance, and grader integrity | `medium-high` | `first-wave` |
| `src_bnm_e1cfa2bf78c9` | browser verification API | decoupled browser verification design and benchmark API boundaries | `medium` | `second-wave` |
| `src_bnm_e5f985948a0e` | SWE verification and automation | standardized software-task verification, automation scaffolds, and benchmark ops | `medium-high` | `first-wave` |
| `src_bnm_f6e5d4c3b2a1` | failure-heavy code degradation | iterative degradation and correctness under repeated agent interaction | `medium-high` | `first-wave` |
| `src_bnm_facefeed2020` | infra sabotage / network assurance | trace-based assurance and infrastructure-sensitive adversarial tasks | `medium` | `second-wave` |

- source_type_notes:
  - `trajectory corpus` remains the primary direct behavior evidence and should lead both failure extraction and mechanism validation.
  - `mirrored harness code` remains the strongest implementation evidence because it is directly inspectable rather than only archived as a capture.
  - `standalone src_cod_*` assets are real code evidence, but their archived `artifact.zip` form makes them weaker than mirrored repos unless the title and capture clearly align to a first-wave question.
  - `benchmark captures` and `eval repos` should stay separate from harness mechanisms unless a benchmark contract or judge design clearly shapes runtime behavior.
  - `postmortems`, `issues`, and `informal notes` remain mandatory contradiction and hypothesis-sharpening evidence classes, but they now carry split confidence labels instead of one smoothed class label.
- confidence_notes:
  - High confidence is reserved for directly inspectable primary evidence: mirrored code, concrete trajectory text, benchmark captures with explicit artifacts, and QC-passed captured records with direct local artifacts.
  - Medium and medium-high are now used for heterogeneous subclusters instead of whole evidence classes, especially for standalone `src_cod_*` captures, BigAI-derived analysis, postmortems, issues, and long-form informal notes.
  - Low and low-medium are now used aggressively for anecdotal social captures, narrow changelog/prompt captures, and local placeholder code so they do not ride along beside stronger evidence unnoticed.
- source_or_cluster_level_confidence_splits:

| Cluster or asset family | Confidence | Why |
| --- | --- | --- |
| `research/sources/trajectories/*/*-traj.txt` | `high` | Primary behavior evidence with direct run text. |
| `research/sources/trajectories/*/*.tar.gz` without matching `*-traj.txt` | `medium` | Real run artifacts, but interpretation is weaker without readable trajectory text. |
| `research/analysis/bigai_trace_layer/output/corpus_summary.json`, `question_answers.json`, `exemplar_runs.json`, `final_harness_reconstruction.md` | `medium` | High-value derived indexes, but `coverage_report.json` still reports 87 answered, 7 partial, and 6 irrecoverable question slots. |
| Mirrored repos under `research/sources/codebases/{deepagents,KIRA,a-evolve,langchain,quarantine}` | `high` | Inspectable source trees and stable subsystem paths. |
| High-signal standalone code captures: `src_cod_086db5a6312e`, `src_cod_564b05dcc95b`, `src_cod_ad409dc1ebde`, `src_cod_e231561a3d69` | `medium-high` | Archived code snapshots with titles directly aligned to mechanism/eval questions. |
| Narrow standalone code captures: `src_cod_18ba360eb4b2`, `src_cod_87b73c75d11a`, `src_cod_a1e1a27e13a1`, `src_cod_c7b08f87aeac` | `medium` | Useful but narrower slices, still stored as archives rather than live mirrored trees. |
| Changelog-style standalone capture: `src_cod_c717c148e387` | `low-medium` | Valuable for chronology, weak as a mechanism source on its own. |
| Captured postmortems under `research/sources/postmortems/` | `medium-high` | Concrete artifact text and stronger authored retrospectives than general informal notes, but still retrospective. |
| Long-form informal notes in `research/sources/informal/` excluding `x_*.md` (35 files) | `medium` | High-signal engineering essays and writeups, but not primary behavior evidence. |
| Social captures `research/sources/informal/x_*.md` (67 files) | `low` | Anecdotal, useful mainly for hypothesis generation and vocabulary. |
| `research/sources/issues/` bug/design captures (55 files) | `medium` for concrete bug traces; `low-medium` for discussion-heavy threads | Issue captures are heterogeneous and should be promoted only when the specific thread carries concrete failure or design evidence. |
| Conservative PDF backfills such as `research/intake/records/src_pap_8c2cb08d2c57.json` and `research/intake/records/src_pap_97367f29ebbd.json` | `medium` | Legitimate index entries, but thin metadata should not be mistaken for full paper synthesis. |
| Local target harness code in `blocks/`, `runner/`, `evals/` | `low` | The repo implementation is still intentionally skeletal relative to stronger external assets. |

- informal_signal_notes:
  - High-signal context-engineering cluster: `research/sources/postmortems/src_pmt_350e236460b0/`, `research/sources/informal/cursor_dynamic_context_discovery.md`, and `research/sources/informal/humanlayer_12_factor_agents.md` align on file-backed context retrieval, selective tool loading, and deterministic prefetch.
  - High-signal long-running/governance cluster: `research/sources/postmortems/src_pmt_cddfa4a4dcc6/`, `research/sources/informal/cursor_long_running_agents.md`, and `research/sources/informal/cognition_agent_trace.md` sharpen questions around agent-first repositories, trace legibility, and agent-to-agent review.
  - High-signal monitoring/eval-integrity cluster: `research/sources/informal/openai_monitor_misalignment.md` and `research/sources/postmortems/src_pmt_ca79e818d699/` inform monitoring, triage, and eval discipline, but should feed synthesis questions rather than be treated as benchmark proof.
  - Postmortem captures should outrank duplicate or derivative informal markdown notes when both describe the same underlying article or claim.
- malformed_or_missing_evidence:
  - No accepted intake record still points into `research/sources/trajectories/` or `research/sources/informal/`, so those classes remain organizer-routed rather than intake-indexed.
  - The repaired organizer now includes a first-wave trajectory matrix, but there is still no full machine-readable DeepAgents or Terminus-KIRA analysis layer comparable to `research/analysis/bigai_trace_layer/output/*`.
  - BigAI trace-layer coverage remains imperfect: `coverage_report.json` still reports 7 partial and 6 irrecoverable question slots, and `corpus_summary.json` still indexes only 86 tasks from 89 task directories.
  - `research/analysis/failure_modes.md` remains TODO-only, so the next failure work must still come from trajectories, issues, postmortems, and benchmark assets rather than from an existing synthesis artifact.
  - The 9 standalone `src_cod_*` captures are archived snapshots, not mirrored browseable trees. They are now individually indexed, but their form still limits subsystem inspection depth.
  - Local out-of-intake paper/doc coverage remains numerically unsettled: the adjudicated review cites 75 captured paper/doc dirs outside accepted or rejected manifests, while a direct filesystem recount found 79 with `capture.json` and 86 with any local artifact.
  - Six placeholder/mock canonical-URL records still contaminate the broader accepted corpus per `tracking/collab/stage_02_synthesis/red_team_review/outputs/red_team_review_adjudicated.md`; they stay out of evidence scope only if synthesis is kept on the captured manifest.
- recommended_first_case_studies:
  - `Terminal-control triad`: `headless-terminal` across `BigAI`, `deepagents`, and `terminus-kira`.
  - `Recovery/process-control triad`: `cancel-async-tasks` across all three families.
  - `Stateful recovery triad`: `db-wal-recovery` across all three families, paired with KIRA and DeepAgents source code plus BigAI exemplar support.
  - `Failure-heavy multimodal triad`: `extract-moves-from-video` across all three families.
  - `Failure-heavy coding-control cluster`: `gpt2-codegolf`, keeping the Terminus-KIRA artifact gap explicit.
  - `Branching / repo-state comparison`: `break-filter-js-from-html` plus `git-multibranch`, reconciled against `deepagents`, `KIRA`, `src_cod_564b05dcc95b`, and `src_cod_ad409dc1ebde`.
- stale_or_superseded_prep_artifacts:
  - `tracking/collab/stage_02_synthesis/eval_inventory/outputs/eval_inventory.md` is superseded for first-wave routing by `tracking/collab/stage_02_synthesis/eval_inventory/outputs/eval_metadata_repair.md` plus the repaired manifests.
  - `research/intake/rejected/2026-04-01__current_blocked_accepted_sources.json` is stale and non-authoritative relative to `research/intake/rejected/2026-04-01__accepted_blocked_exceptions.json` plus `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`.
  - `research/analysis/2026-03-31__accepted_corpus_local_capture_audit.md` and `.tsv` are historical diagnostics against an older 103-source accepted state, not the current 288/247/41 frozen partition.
  - The individual review drafts under `tracking/collab/stage_02_synthesis/red_team_review/outputs/red_team_review_{codex,gemini,opus}.md` are superseded by `tracking/collab/stage_02_synthesis/red_team_review/outputs/red_team_review_adjudicated.md`.
- first_deep_synthesis_priorities:
  - Do not open a deep-synthesis artifact yet. The next required move after this repair remains the targeted rerun review of `organizer.md`.
  - If the rerun accepts the organizer, re-decide between `mechanism_map` and `failure_taxonomy` using the repaired trajectory matrix and codebase/eval matrix rather than the earlier prose-only priority lists.
  - The strongest first-wave evidence lanes after acceptance are now clearer: terminal control, process/recovery control, stateful recovery, failure-heavy multimodal behavior, and eval/replay infrastructure.
  - Variant-family work remains downstream of that decision and should not be opened from this organizer alone.
- blockers:
  - Stage 2A remains blocked on one targeted adversarial rerun against the repaired `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`.
  - Any agent that reads from the broader 288-source accepted manifest instead of the captured 247-source manifest will reintroduce blocked-exception and false-provenance contamination.
  - The paper/doc out-of-intake recount discrepancy remains unresolved and should be treated as a corpus-trust caveat until reconciled.
- synthesis_prep_completion_judgment:
  - This repaired organizer is intended to satisfy the missing inventory-granularity requirements from `SYNTHESIS_PREP_CHECKLIST.md`, but synthesis prep is still not complete yet.
  - One more prep artifact is still required: the rerun targeted synthesis-prep red-team review at `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/red_team.md`.
  - Only after that rerun should the project re-decide whether `mechanism_map` or `failure_taxonomy` is the first deep-synthesis artifact.
- next_hand_off_target:
  - `synthesis-prep red-team reviewer`, writing `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/red_team.md`
