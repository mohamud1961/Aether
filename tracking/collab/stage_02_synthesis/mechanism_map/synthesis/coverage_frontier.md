# Mechanism Map Coverage Frontier

Date: 2026-04-04

Current status

- Accepted wave history so far:
  - `wave_01_exploratory_anchor`
- Artifact completion status:
  - not complete
- Governing rule:
  - do not open new `mechanism_map` waves until `coverage_access` Wave 01 and Wave 02 complete

coverage_used

- `research/sources/trajectories/{BigAI,deepagents,terminus-kira}/{headless-terminal,cancel-async-tasks,db-wal-recovery,break-filter-js-from-html,git-multibranch}/*-traj.txt`
- `research/sources/trajectories/{BigAI,deepagents,terminus-kira}/{headless-terminal,cancel-async-tasks,torch-pipeline-parallelism}/*.tar.gz`
- `research/sources/codebases/KIRA/`
- `research/sources/codebases/deepagents/`
- `research/sources/codebases/a-evolve/`
- `research/sources/codebases/src_cod_*/capture.json`
- sampled reads from `research/sources/codebases/src_cod_*/artifact.zip`
- `research/sources/docs/bigai/translated/*.md`
- selected `research/sources/docs/src_doc_*/artifact.txt`
- selected `research/sources/informal/*.md`
- selected `research/sources/issues/src_iss_*/`
- selected `research/sources/postmortems/src_pmt_*/`
- selected `research/sources/benchmarks/src_bnm_*/{capture.json,artifact.txt}`
- `research/analysis/bigai_trace_layer/output/`
- `blocks/`
- `runner/`
- `evals/`

coverage_not_yet_used

- `research/sources/papers/papers_text/` whole surface not yet created
- `research/sources/papers/*.pdf` content not yet extracted
- `research/sources/codebases/quarantine/claw-code/`
- full traversal of `research/sources/codebases/src_cod_*/artifact.zip`
- `research/sources/trajectories/{BigAI,deepagents,terminus-kira}/extract-moves-from-video/*`
- `research/sources/trajectories/{BigAI,deepagents,terminus-kira}/gpt2-codegolf/*`
- most long-tail trajectory task families outside the Wave 01 shared slices
- most `research/sources/informal/*.md`
- most `research/sources/issues/src_iss_*/`
- most `research/sources/postmortems/src_pmt_*/`
- benchmark implementation code behind `research/sources/benchmarks/src_bnm_*/artifact.html`

priority_sources_not_yet_read

- `research/sources/papers/src_pap_f6aa42bfdc1a/artifact.pdf`
- `research/sources/papers/src_pap_c5f42ff16ea3/artifact.pdf`
- `research/sources/codebases/quarantine/claw-code/`
- `research/sources/trajectories/{BigAI,deepagents,terminus-kira}/extract-moves-from-video/*`
- `research/sources/trajectories/{BigAI,deepagents,terminus-kira}/gpt2-codegolf/*`
- `research/sources/issues/src_iss_*/`
- `research/sources/informal/*.md`

wave_02_readiness_note

- `mechanism_map` Wave 02 should not open yet.
- The next governed coverage work is:
  - `coverage_access` Wave 01 `formal_access_closure`
  - `coverage_access` Wave 02 `source_system_promotion_and_map`
