# Tracing Readiness

Date: 2026-04-02

TRACING_READINESS_OUTPUT
- artifact: `tracing_readiness`
- scope:
  - This is a bounded pre-Stage-2B readiness artifact for the routed trajectory corpus. It inventories trajectory usability, linkage quality, and evidence gaps without opening `mechanism_map` or `failure_taxonomy`.
  - Evidence read for this pass:
    - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`
    - `tracking/collab/stage_02_synthesis/deep_synthesis_plan/synthesis/principal_synthesis.md`
    - `TRAJECTORY_SOURCE_CASE_STUDY_TEMPLATE.md`
    - `research/sources/trajectories/BigAI/`
    - `research/sources/trajectories/deepagents/`
    - `research/sources/trajectories/terminus-kira/`
    - `research/analysis/bigai_trace_layer/output/`
    - `research/sources/codebases/deepagents/`
    - `research/sources/codebases/KIRA/`
    - `research/sources/codebases/langchain/`
    - `research/sources/benchmarks/`
    - `blocks/`
    - `runner/`
    - `evals/`
- operating_rules:
  - Behavior claims must anchor in readable trajectory artifacts first: `research/sources/trajectories/*/*-traj.txt` whenever present.
  - Implementation claims must anchor in visible source first: `research/sources/codebases/deepagents/`, `research/sources/codebases/KIRA/`, and other routed source trees before any cross-run interpretation.
  - Eval or benchmark-contract claims must anchor in visible eval or benchmark artifacts first: `research/sources/codebases/deepagents/libs/evals/`, `research/sources/codebases/langchain/agentevals/`, `research/sources/codebases/langchain/openevals/`, and `research/sources/benchmarks/`.
  - When trajectory evidence and source evidence disagree, preserve the disagreement explicitly instead of smoothing it over.
  - `research/analysis/*` outputs are routing aids and case selectors. They do not replace the underlying trajectory, source, or benchmark paths.
  - Local harness code in `blocks/`, `runner/`, and `evals/` is in scope only for linkage and gap notes in this artifact, not as a substitute for the frozen external tracing corpus.

## Corpus Coverage Summary

Trajectory corpus coverage was checked directly from the family roots under `research/sources/trajectories/`.

| Family | Task dirs | Tasks with readable direct trajectory text | Tar-only tasks | Empty task dirs | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| `BigAI` | 89 | 76 | 10 | 3 | Multiple runs per task are common; strongest within-task comparison value. |
| `deepagents` | 89 | 85 | 3 | 1 | Usually one readable run bundle per task; strongest trace-to-source-to-eval linkage. |
| `terminus-kira` | 89 | 84 | 5 | 0 | Usually one run per task; strong visible harness source linkage. |

- Cross-family direct-text overlap:
  - 69 tasks have readable `*-traj.txt` artifacts in all three families.
  - The first-wave priority set with readable direct text in all three families is:
    - `headless-terminal`
    - `cancel-async-tasks`
    - `db-wal-recovery`
    - `extract-moves-from-video`
    - `break-filter-js-from-html`
    - `git-multibranch`
  - The first-wave priority set with a known direct-text gap is:
    - `gpt2-codegolf` because `research/sources/trajectories/terminus-kira/gpt2-codegolf/` currently has only `0b44fad6-7d6b-44a5-a9df-9f2bdeaf68bf.tar.gz`.
- BigAI derived-analysis coverage:
  - `research/analysis/bigai_trace_layer/output/corpus_summary.json` indexes 86 tasks from a 89-task directory tree.
  - `research/analysis/bigai_trace_layer/output/coverage_report.json` reports 87 answered, 7 partial, and 6 irrecoverable question slots.
  - `research/analysis/bigai_trace_layer/output/exemplar_runs.json` gives useful run selectors, but it remains a routing layer rather than a direct behavior artifact.

Evidence paths:
- `research/sources/trajectories/BigAI/`
- `research/sources/trajectories/deepagents/`
- `research/sources/trajectories/terminus-kira/`
- `research/analysis/bigai_trace_layer/output/corpus_summary.json`
- `research/analysis/bigai_trace_layer/output/coverage_report.json`
- `research/analysis/bigai_trace_layer/output/exemplar_runs.json`

## Family-By-Family Readiness Summary

### BigAI

- Ready now:
  - BigAI is immediately usable for first-wave cases that have readable `*-traj.txt` artifacts, especially where multiple runs exist for the same task and allow within-family comparison.
  - The cleanest ready-now BigAI tasks for Deep Synthesis tracing are:
    - `headless-terminal`
    - `cancel-async-tasks`
    - `db-wal-recovery`
    - `extract-moves-from-video`
    - `gpt2-codegolf`
    - `break-filter-js-from-html`
    - `git-multibranch`
- Usable with caution:
  - Tar-only BigAI tasks:
    - `dna-assembly`
    - `dna-insert`
    - `extract-elf`
    - `filter-js-from-html`
    - `fix-ocaml-gc`
    - `gcode-to-text`
    - `llm-inference-batching-scheduler`
    - `make-doom-for-mips`
    - `make-mips-interpreter`
    - `pytorch-model-cli`
  - These tasks retain real bundle artifacts, but direct behavior claims are weaker unless the tarball is unpacked or a matching readable trajectory appears elsewhere.
- Weak / gap / malformed:
  - Empty BigAI task dirs:
    - `financial-document-processor`
    - `install-windows-3.11`
    - `sparql-university`
  - BigAI has the strongest trace-side behavior coverage but no mirrored BigAI harness source tree in the current input set, so source-side mechanism claims cannot be attributed to BigAI implementation directly from this corpus slice.
  - `research/analysis/bigai_trace_layer/output/` is helpful for routing, but not enough to erase missing direct text or missing source.

Evidence paths:
- `research/sources/trajectories/BigAI/headless-terminal/`
- `research/sources/trajectories/BigAI/cancel-async-tasks/`
- `research/sources/trajectories/BigAI/db-wal-recovery/`
- `research/sources/trajectories/BigAI/extract-moves-from-video/`
- `research/sources/trajectories/BigAI/gpt2-codegolf/`
- `research/sources/trajectories/BigAI/break-filter-js-from-html/`
- `research/sources/trajectories/BigAI/git-multibranch/`
- `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
- `research/analysis/bigai_trace_layer/output/task_index.json`

### deepagents

- Ready now:
  - DeepAgents is the strongest family for immediate trajectory/source case-study work because readable direct trajectories, mirrored implementation code, and explicit Terminal Bench eval infrastructure are all local.
  - The cleanest ready-now DeepAgents tasks for Deep Synthesis tracing are:
    - `headless-terminal`
    - `cancel-async-tasks`
    - `db-wal-recovery`
    - `extract-moves-from-video`
    - `gpt2-codegolf`
    - `break-filter-js-from-html`
    - `git-multibranch`
- Usable with caution:
  - Tar-only DeepAgents tasks:
    - `git-leak-recovery`
    - `install-windows-3.11`
    - `prove-plus-comm`
  - These remain useful for routing and comparative coverage, but not for strong first-pass behavior claims.
- Weak / gap / malformed:
  - Empty DeepAgents task dir:
    - `qemu-startup`
  - DeepAgents usually provides only one captured run per task, so it is stronger for trace-to-source reconciliation than for within-family variance analysis.

Evidence paths:
- `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
- `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
- `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
- `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
- `research/sources/trajectories/deepagents/gpt2-codegolf/2886c1b1-248c-4f61-ae08-020f2b466065-traj.txt`
- `research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py`
- `research/sources/codebases/deepagents/libs/deepagents/deepagents/base_prompt.md`
- `research/sources/codebases/deepagents/libs/evals/README.md`
- `research/sources/codebases/deepagents/libs/evals/scripts/analyze.py`

### terminus-kira

- Ready now:
  - Terminus-KIRA is immediately usable where a readable `*-traj.txt` exists because the main harness source and prompt surface are directly visible in-repo.
  - The cleanest ready-now Terminus-KIRA tasks for Deep Synthesis tracing are:
    - `headless-terminal`
    - `cancel-async-tasks`
    - `db-wal-recovery`
    - `extract-moves-from-video`
    - `break-filter-js-from-html`
    - `git-multibranch`
- Usable with caution:
  - Tar-only Terminus-KIRA tasks:
    - `adaptive-rejection-sampler`
    - `code-from-image`
    - `fix-code-vulnerability`
    - `gpt2-codegolf`
    - `prove-plus-comm`
  - `gpt2-codegolf` remains high value, but the missing readable KIRA trajectory makes it a second-wave failure case rather than a first-pass anchor.
- Weak / gap / malformed:
  - No empty Terminus-KIRA task dirs were found in this pass.
  - Terminus-KIRA has good visible harness code, but a thinner explicit eval-side surface than DeepAgents in the current local corpus.

Evidence paths:
- `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
- `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
- `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
- `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
- `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
- `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt`
- `research/sources/codebases/KIRA/README.md`
- `research/sources/codebases/KIRA/run-scripts/run_docker.sh`

## Readiness Buckets

### Ready Now

- `headless-terminal`
- `cancel-async-tasks`
- `db-wal-recovery`
- `extract-moves-from-video`
- `break-filter-js-from-html`
- `git-multibranch`

Reason:
- Each case has readable direct trajectory text across all three families.
- Each case can be linked to visible DeepAgents and Terminus-KIRA source surfaces.
- Each case can be linked to at least one local eval or benchmark-contract surface.

### Usable With Caution

- `gpt2-codegolf`
  - High-value failure-heavy case with readable BigAI and DeepAgents direct text, but tar-only Terminus-KIRA coverage.
- `gcode-to-text`
  - Readable DeepAgents and Terminus-KIRA trajectories exist, but BigAI is tar-only and `research/analysis/bigai_trace_layer/output/exemplar_runs.json` flags a provenance-only bundle.
- `install-windows-3.11`
  - Readable Terminus-KIRA coverage exists, DeepAgents is tar-only, and BigAI task dir is empty.
- `git-leak-recovery`
  - Readable BigAI and Terminus-KIRA coverage exists, but DeepAgents is tar-only.
- `qemu-startup`
  - Readable BigAI and Terminus-KIRA coverage exists, but DeepAgents task dir is empty.

### Weak / Gap / Malformed

- `prove-plus-comm`
  - Readable BigAI coverage exists, but DeepAgents and Terminus-KIRA are both tar-only.
- `financial-document-processor`
- `sparql-university`
  - BigAI empty task dirs with no compensating evidence from the current input set.
- Any case that depends primarily on `research/analysis/bigai_trace_layer/output/*` without a readable trajectory or visible source path.

Evidence paths:
- `research/sources/trajectories/terminus-kira/gpt2-codegolf/0b44fad6-7d6b-44a5-a9df-9f2bdeaf68bf.tar.gz`
- `research/sources/trajectories/BigAI/gcode-to-text/`
- `research/analysis/bigai_trace_layer/output/exemplar_runs.json`
- `research/sources/trajectories/deepagents/install-windows-3.11/2873a57c-fa19-44fb-a8c7-0fd5f2306444.tar.gz`
- `research/sources/trajectories/deepagents/qemu-startup/`
- `research/sources/trajectories/deepagents/prove-plus-comm/e4e670dd-4a41-4366-a1ca-fc78daca1471.tar.gz`
- `research/sources/trajectories/terminus-kira/prove-plus-comm/790cd7ff-9610-46c7-bd4d-b86abf611418.tar.gz`

## Task / Case-Study Priority Queue

### First-wave case studies

- `P1 headless-terminal` (`ready_now`)
  - Direct trajectory paths:
    - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
    - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
    - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
  - Source linkage:
    - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/base_prompt.md`
  - Eval / benchmark / conceptual linkage:
    - `research/sources/codebases/deepagents/libs/evals/README.md`
    - `research/sources/codebases/langchain/agentevals/README.md`
    - `research/sources/benchmarks/src_bnm_facefeed2020/artifact.txt`
  - Why first:
    - Best terminal-control comparison starter with readable behavior in all three families and visible harness mechanisms in two.

- `P1 cancel-async-tasks` (`ready_now`)
  - Direct trajectory paths:
    - `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
    - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
    - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - Source linkage:
    - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/subagents.py`
  - Eval / benchmark / conceptual linkage:
    - `research/sources/codebases/deepagents/libs/evals/scripts/analyze.py`
    - `research/sources/codebases/langchain/agentevals/README.md`
    - `research/sources/benchmarks/src_bnm_facefeed2020/artifact.txt`
  - Why first:
    - Clean process-control and recovery case with readable direct traces across all families.

- `P1 db-wal-recovery` (`ready_now`)
  - Direct trajectory paths:
    - `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`
    - `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
    - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  - Source linkage:
    - `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt`
    - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/base_prompt.md`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/filesystem.py`
  - Eval / benchmark / conceptual linkage:
    - `research/sources/codebases/deepagents/libs/evals/README.md`
    - `research/sources/codebases/deepagents/libs/evals/scripts/analyze.py`
    - `research/sources/benchmarks/src_bnm_e5f985948a0e/artifact.txt`
    - `research/sources/benchmarks/src_bnm_8c3b5dc456f5/artifact.txt`
  - Why first:
    - Strong stateful-recovery case with explicit verifier and safety-handling value; BigAI also has a named exemplar in `research/analysis/bigai_trace_layer/output/exemplar_runs.json`.

- `P1 extract-moves-from-video` (`ready_now`)
  - Direct trajectory paths:
    - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
    - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
    - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
  - Source linkage:
    - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - `research/sources/codebases/KIRA/README.md`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py`
  - Eval / benchmark / conceptual linkage:
    - `research/sources/codebases/langchain/openevals/README.md`
    - `research/sources/codebases/langchain/agentevals/README.md`
    - `research/sources/benchmarks/src_bnm_e1cfa2bf78c9/artifact.txt`
  - Why first:
    - Failure-heavy multimodal case with readable direct behavior in all three families and a visible multimodal mechanism on the KIRA side.

- `P2 gpt2-codegolf` (`usable_with_caution`)
  - Direct trajectory paths:
    - `research/sources/trajectories/BigAI/gpt2-codegolf/170986fa-f818-4d0f-9bbd-21f495f4ad9f-traj.txt`
    - `research/sources/trajectories/deepagents/gpt2-codegolf/2886c1b1-248c-4f61-ae08-020f2b466065-traj.txt`
    - `research/sources/trajectories/terminus-kira/gpt2-codegolf/0b44fad6-7d6b-44a5-a9df-9f2bdeaf68bf.tar.gz`
  - Source linkage:
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py`
    - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
  - Eval / benchmark / conceptual linkage:
    - `research/sources/codebases/deepagents/libs/evals/scripts/analyze.py`
    - `research/sources/benchmarks/src_bnm_f6e5d4c3b2a1/artifact.txt`
    - `research/sources/benchmarks/src_bnm_8c3b5dc456f5/artifact.txt`
  - Why first:
    - High-value failure-heavy coding-control case, but the missing readable KIRA direct text prevents using it as the very first trace anchor.

- `P2 break-filter-js-from-html` (`ready_now`)
  - Direct trajectory paths:
    - `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
    - `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`
    - `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`
  - Source linkage:
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/filesystem.py`
    - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - `research/analysis/bigai_trace_layer/output/exemplar_runs.json`
  - Eval / benchmark / conceptual linkage:
    - `research/sources/codebases/deepagents/libs/evals/README.md`
    - `research/sources/benchmarks/src_bnm_e5f985948a0e/artifact.txt`
    - `research/sources/benchmarks/src_bnm_f6e5d4c3b2a1/artifact.txt`
  - Why first:
    - Good branching and coordination case; BigAI also exposes a rare explicit executor-to-executor ask in the derived index.

- `P2 git-multibranch` (`ready_now`)
  - Direct trajectory paths:
    - `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`
    - `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
    - `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
  - Source linkage:
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/filesystem.py`
    - `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt`
    - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
  - Eval / benchmark / conceptual linkage:
    - `research/sources/codebases/deepagents/libs/evals/README.md`
    - `research/sources/benchmarks/src_bnm_e5f985948a0e/artifact.txt`
    - `research/sources/benchmarks/src_bnm_f6e5d4c3b2a1/artifact.txt`
  - Why first:
    - Strong repo-state and cleanup comparison case with readable direct traces across all three families.

### High-value lower-readiness cases

- `gcode-to-text`
  - Cross-family comparison is weakened by BigAI tar-only coverage and a provenance-only exemplar note in `research/analysis/bigai_trace_layer/output/exemplar_runs.json`.
- `install-windows-3.11`
  - Cross-family comparison is weakened by BigAI empty coverage and DeepAgents tar-only coverage.
- `qemu-startup`
  - Cross-family comparison is weakened by an empty DeepAgents task dir.
- `git-leak-recovery`
  - Cross-family comparison is weakened by tar-only DeepAgents coverage.
- `prove-plus-comm`
  - Cross-family comparison is weakened by tar-only DeepAgents and Terminus-KIRA coverage.

## Trajectory-To-Source Linkage Notes

- `BigAI`
  - Strongest for behavior-first work because multiple runs per task are often available.
  - Weakest for implementation-first work in this input set because no mirrored BigAI harness repo was provided alongside the trajectories.
  - Use `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md` and `research/analysis/bigai_trace_layer/output/exemplar_runs.json` only as selectors and routing aids, not as source substitutes.

- `deepagents`
  - Best trace-to-source chain in the current repo-local corpus:
    - behavior: `research/sources/trajectories/deepagents/`
    - harness source: `research/sources/codebases/deepagents/libs/deepagents/deepagents/`
    - eval source: `research/sources/codebases/deepagents/libs/evals/`
  - The visible linkage points most likely to matter for Deep Synthesis tracing are:
    - planning and prompt surfaces: `research/sources/codebases/deepagents/libs/deepagents/deepagents/base_prompt.md`
    - loop structure: `research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py`
    - filesystem and context surfaces: `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/filesystem.py`
    - subagent surfaces: `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/subagents.py`

- `terminus-kira`
  - Best visible mechanism surface for terminal-native tool use in the current corpus:
    - behavior: `research/sources/trajectories/terminus-kira/`
    - harness source: `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - prompt surface: `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt`
  - Visible linkage points most likely to matter for Deep Synthesis tracing are:
    - native tool definitions: `execute_commands`, `task_complete`, and `image_read` in `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - marker-based polling and output filtering in `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - summarization fallback and trajectory splitting in `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - final state-minimization rule in `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt`

- Local harness gap note
  - `blocks/README.md`, `runner/agent.py`, `runner/logger.py`, `runner/evaluator.py`, and `evals/README.md` show the intended lego-block and logging architecture, but they remain too skeletal to serve as a strong trace-side comparator against the external harnesses.

Evidence paths:
- `blocks/README.md`
- `runner/agent.py`
- `runner/logger.py`
- `runner/evaluator.py`
- `evals/README.md`

## Trajectory-To-Eval Linkage Notes

- DeepAgents has the clearest eval linkage in the current corpus:
  - `research/sources/codebases/deepagents/libs/evals/README.md` explicitly ties Deep Agents to Harbor, Terminal Bench 2.0, automatic verification, reward scoring, and ATIF trajectory logging.
  - `research/sources/codebases/deepagents/libs/evals/scripts/analyze.py` explicitly expects `agent/trajectory.json` and `verifier/reward.txt`, which makes it the strongest local bridge between trajectory reading and verifier status.
  - `research/sources/codebases/deepagents/libs/evals/scripts/harbor_langsmith.py` links Harbor job results to LangSmith traces and reward feedback.

- Terminus-KIRA has a visible execution harness but a thinner explicit eval layer:
  - `research/sources/codebases/KIRA/README.md` and `research/sources/codebases/KIRA/run-scripts/run_docker.sh` show Harbor-based Terminal Bench execution.
  - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py` clearly records trajectory steps and dumps trajectories, but the current corpus does not expose a DeepAgents-style separate eval-analysis package for KIRA.

- LangChain eval repos are comparator surfaces, not direct evidence of these specific runs:
  - `research/sources/codebases/langchain/agentevals/README.md` is directly relevant for trajectory-match and trajectory-judge patterns.
  - `research/sources/codebases/langchain/openevals/README.md` contributes general LLM-as-judge, code, multimodal, and trajectory-eval patterns.
  - These repos are best used to interpret how later eval implications might be framed, not to override direct run evidence.

- Benchmark captures under `research/sources/benchmarks/` are also comparator and contract surfaces rather than direct task-specific ground truth for the frozen run set:
  - `research/sources/benchmarks/src_bnm_8c3b5dc456f5/artifact.txt` for cheating/specification-gaming pressure.
  - `research/sources/benchmarks/src_bnm_e1cfa2bf78c9/artifact.txt` for verifiable environment generation and evaluation.
  - `research/sources/benchmarks/src_bnm_e5f985948a0e/artifact.txt` for verified coding-task automation and evaluation discipline.
  - `research/sources/benchmarks/src_bnm_f6e5d4c3b2a1/artifact.txt` for iterative degradation and correctness pressure in coding tasks.
  - `research/sources/benchmarks/src_bnm_facefeed2020/artifact.txt` for trace-based assurance and troubleshooting trajectories.

## Missing Or Malformed Evidence Notes

- There is no mirrored BigAI implementation tree in the current input set. That is the main reason BigAI is stronger for behavior-first tracing than for implementation-side reconciliation.
- BigAI trace-layer analysis is incomplete relative to the raw family directory:
  - `research/analysis/bigai_trace_layer/output/corpus_summary.json` indexes 86 tasks from 89 task dirs.
  - `research/analysis/bigai_trace_layer/output/coverage_report.json` still reports partial and irrecoverable slots.
- Several high-value cross-family cases still have direct-text gaps:
  - `research/sources/trajectories/terminus-kira/gpt2-codegolf/`
  - `research/sources/trajectories/deepagents/git-leak-recovery/`
  - `research/sources/trajectories/deepagents/install-windows-3.11/`
  - `research/sources/trajectories/deepagents/prove-plus-comm/`
  - `research/sources/trajectories/terminus-kira/prove-plus-comm/`
- Some task dirs are empty rather than merely tar-only:
  - `research/sources/trajectories/BigAI/financial-document-processor/`
  - `research/sources/trajectories/BigAI/install-windows-3.11/`
  - `research/sources/trajectories/BigAI/sparql-university/`
  - `research/sources/trajectories/deepagents/qemu-startup/`
- The local harness code does not yet provide a rich internal tracing substrate for external comparison:
  - `runner/logger.py` is still only a responsibility stub.
  - `runner/evaluator.py` is still only a responsibility stub.
  - `runner/agent.py` is still only a composition stub.

## Recommended First Tracing Case Studies For Deep Synthesis

Use `TRAJECTORY_SOURCE_CASE_STUDY_TEMPLATE.md` directly for the first-wave case-study writeups.

1. `headless-terminal`
   - Best clean terminal-control starter.
2. `cancel-async-tasks`
   - Best process-control and cleanup starter.
3. `db-wal-recovery`
   - Best stateful-recovery and verifier-discipline starter.
4. `extract-moves-from-video`
   - Best failure-heavy multimodal starter.
5. `break-filter-js-from-html`
   - Best branching and coordination follow-on.
6. `git-multibranch`
   - Best repo-state and cleanup follow-on.
7. `gpt2-codegolf`
   - First high-value caution case after the ready-now set, because it tests whether the tracing workflow handles missing readable direct text in one family without overclaiming.

## Judgment On Whether Tracing Is Ready Enough To Support `mechanism_map`

Tracing is ready enough to support a bounded, first-wave `mechanism_map` pass only if Deep Synthesis is explicitly opened and the pass stays inside the ready-now case set plus clearly labeled caution cases.

That judgment is conditional, not blanket:

- Yes for:
  - first-wave behavior-first/source-first case studies anchored on `headless-terminal`, `cancel-async-tasks`, `db-wal-recovery`, `extract-moves-from-video`, `break-filter-js-from-html`, and `git-multibranch`
  - source reconciliation that leans primarily on `research/sources/codebases/deepagents/` and `research/sources/codebases/KIRA/`
- Not yet for:
  - unconstrained full-corpus mechanism claims
  - BigAI implementation claims that pretend the missing source tree is visible
  - failure-heavy cases that depend on tar-only or empty task dirs without explicit caveats

Bottom line:

- The tracing corpus is sufficiently prepared for disciplined Deep Synthesis opening on selected case studies.
- The tracing corpus is not sufficiently uniform to justify a by-inertia or whole-corpus `mechanism_map` pass with no readiness caveats.
