# Open Questions

Unresolved issues that materially affect the research direction.

## OQ-001 | Is the six-dimension harness taxonomy sufficient?
- Why it matters: Experiment design and block interfaces depend on whether orientation, tools, execution, context, verification, and recovery are the full set of meaningful axes.
- Observations: `research/analysis/lego_dimensions.md` explicitly asks whether dimensions are missing. `research/red_team_handoff.md` asks whether there is a seventh axis and whether prompt engineering should be its own dimension. `research/intake/normalized/manifests/policy_program__accepted.json` has accepted sources, while `environment_substrate__accepted.json` is empty.
- What is missing: An evidence-backed decision on whether policy-program, prompting, or environment substrate should become first-class experimental dimensions.
- Evidence paths: `research/analysis/lego_dimensions.md`, `research/red_team_handoff.md`, `research/intake/normalized/manifests/policy_program__accepted.json`, `research/intake/normalized/manifests/environment_substrate__accepted.json`
- Confidence: high that this remains unresolved

## OQ-002 | Why do 89 BigAI task directories reduce to 86 indexed tasks in the derived summary?
- Why it matters: Baseline clarity and reproducibility depend on knowing exactly what the derived trace layer covers.
- Observations: There are 89 directories under `research/sources/trajectories/BigAI`, but `research/analysis/bigai_trace_layer/output/corpus_summary.json` reports only 86 indexed tasks. The omitted task directories are `financial-document-processor`, `install-windows-3.11`, and `sparql-university`.
- What is missing: Either a build-rule explanation for the exclusions or recovered artifacts that let those tasks enter the derived corpus.
- Evidence paths: `research/sources/trajectories/README.md`, `research/sources/trajectories/BigAI/`, `research/analysis/bigai_trace_layer/output/corpus_summary.json`
- Confidence: high

## OQ-003 | Does observable executor fanout imply true parallel branching or only sequential reassignment?
- Why it matters: Execution-block design changes materially depending on whether the harness really branches in parallel.
- Observations: `research/analysis/bigai_trace_layer/output/question_answers.json` reports 123 multi-executor runs and max observed fanout of 5, but ARCH-06 remains only partial. Explicit executor-to-executor `ask` appears to be rare.
- What is missing: Scheduler-level traces, controller code, or richer timing information that can distinguish real parallelism from sequential worker reassignment.
- Evidence paths: `research/analysis/bigai_trace_layer/output/question_answers.json`, `research/analysis/bigai_trace_layer/output/exemplar_runs.json`
- Confidence: high

## OQ-004 | How should zero-coverage intake buckets be handled?
- Why it matters: Under-covered dimensions can silently bias block design and experiment order.
- Observations: Six accepted-manifest files contain zero accepted sources: artifact workspace, cost/token management, environment substrate, evals/benchmarking, memory, and observability/audit.
- What is missing: A follow-on intake plan or an explicit scope cut that says those dimensions are out of scope for the current iteration.
- Evidence paths: `research/intake/normalized/manifests/artifact_workspace__accepted.json`, `research/intake/normalized/manifests/cost_token_management__accepted.json`, `research/intake/normalized/manifests/environment_substrate__accepted.json`, `research/intake/normalized/manifests/evals_benchmarking__accepted.json`, `research/intake/normalized/manifests/memory__accepted.json`, `research/intake/normalized/manifests/observability_audit__accepted.json`
- Confidence: high

## OQ-005 | Is the proposed experiment/eval methodology actually ratified, or still only a draft for review?
- Why it matters: Budgeting, sequencing, and future paper claims should not rely on a proposal being treated as a settled decision.
- Observations: `research/red_team_handoff.md` labels the methodology as "Current Proposal" and asks for adversarial review. `experiments/results/scoreboard.md` is TODO-only, and no experiment result artifacts were found in the inspected `experiments/results/` directory beyond that placeholder.
- What is missing: A post-review decision record or superseding methodology document that turns the proposal into an active research plan.
- Evidence paths: `research/red_team_handoff.md`, `experiments/README.md`, `experiments/results/scoreboard.md`
- Confidence: medium-high

## OQ-006 | Which seed patterns are durable enough to survive into the paper-quality evidence base?
- Why it matters: Early synthesis can quietly become lore if it is not either linked to evidence or explicitly superseded.
- Observations: `research/analysis/patterns.md` contains seed patterns and `research/references.md` contains only a short seed table. `research/analysis/failure_modes.md` remains unpopulated.
- What is missing: Evidence-linked pattern entries, contradiction handling, and a populated failure taxonomy.
- Evidence paths: `research/analysis/patterns.md`, `research/references.md`, `research/analysis/failure_modes.md`
- Confidence: high

## OQ-007 | How should the 2026-03-29 supplemental sweep outputs be promoted into the audited corpus?
- Why it matters: Raw inbox records are not yet reliable enough for stable bucket counts, claims, or decisions.
- Observations: Three non-empty 2026-03-29 supplemental files contribute 58 raw records, but the paired dispatcher, QC, and dedupe outputs are empty, and the newest normalized artifacts remain dated 2026-03-25.
- What is missing: A completed normalization/dedupe/QC pass or an explicit decision that the 2026-03-29 supplemental pass should be excluded from the audited corpus.
- Evidence paths: `research/intake/inbox/supplemental_runs/2026-03-29__approval_control_gates_sweep.json`, `research/intake/inbox/supplemental_runs/2026-03-29__dynamic_tool_discovery_prefetch_sweep.json`, `research/intake/inbox/supplemental_runs/2026-03-29__experiment_methodology_online_offline_alignment_sweep.json`, `research/intake/inbox/system_runs/2026-03-29__dispatcher__dispatch_plan.json`, `research/intake/inbox/system_runs/2026-03-29__qc__pass_01.json`, `research/intake/inbox/system_runs/2026-03-29__dedup__pass_01.json`, `research/intake/normalized/2026-03-25__response_object.json`
- Confidence: high
