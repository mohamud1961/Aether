# Claims

Candidate paper claims with evidence, caveats, and confidence.

## C-001 | Stable planner-before-executor protocol in parseable BigAI runs
- Status: candidate
- Claim: In the parseable BigAI corpus, observable harness behavior follows a stable planner-before-executor role protocol rather than a flat single-agent loop.
- Evidence: `research/analysis/bigai_trace_layer/output/question_answers.json` reports a stable role set across parseable runs and 312/312 planner-before-executor ordering in ARCH-01 and ARCH-02. The cited exemplar is `research/sources/trajectories/BigAI/adaptive-rejection-sampler/c05344ea-9a06-490d-9310-937670fb7b4a.tar.gz`.
- Caveats: This claim is about observable roles only; hidden scheduler/controller implementation details remain unknown.
- Confidence: high

## C-002 | Early explicit planning is a near-universal observable doctrine in BigAI
- Status: candidate
- Claim: The BigAI planner writes an explicit plan at the very start of almost every parseable run.
- Evidence: `research/analysis/bigai_trace_layer/output/question_answers.json` PLAN-01 and PLAN-02 report the first `save_plan` at step 3 in 310 runs and step 4 in 2 runs.
- Caveats: This supports presence and timing of explicit plans, not plan quality or causal impact on task success.
- Confidence: high

## C-003 | Verification and recovery are explicit and often successful components of the observed harness
- Status: candidate
- Claim: Verification is a first-class observable role in many successful BigAI runs, and verifier-failure recovery often succeeds.
- Evidence: ARCH-03 in `research/analysis/bigai_trace_layer/output/question_answers.json` reports verifier presence in 272/312 parseable runs and in 247/255 parseable passes. REC-01 through REC-06 report 63 runs with verifier failure, 57 of which recovered to a final verifier pass.
- Caveats: The evidence is observational. Verifier presence may correlate with easier-to-finish runs, while verifier absence may reflect timeouts or hidden controller policy.
- Confidence: medium-high

## C-004 | Multi-executor behavior is observable, but true parallelism is not established
- Status: candidate
- Claim: The BigAI corpus shows executor fanout beyond a single worker, but public traces do not prove true concurrent execution.
- Evidence: ARCH-04 through ARCH-06 in `research/analysis/bigai_trace_layer/output/question_answers.json` report 189 single-executor runs, 123 multi-executor runs, and max observed executor fanout of 5. The same section notes that explicit executor-to-executor `ask` happens only once, in `break-filter-js-from-html`.
- Caveats: This is partly an anti-claim: the evidence supports branching/fanout observation, but not the stronger claim of true parallel execution.
- Confidence: medium-high

## C-005 | Corpus-only post-hoc tracing recovered most, but not all, predefined BigAI research questions
- Status: candidate
- Claim: A contamination-aware, corpus-only trace layer over public BigAI bundles recovered answers for most predefined research questions while preserving explicit unknowns.
- Evidence: `research/analysis/bigai_trace_layer/output/coverage_report.json` reports 100 total questions, with 87 answered, 7 partial, and 6 irrecoverable. The README states that the method excludes official task source, hidden tests, and raw-bundle mutation.
- Caveats: This result is specific to the current question catalog and corpus; it is not a general guarantee for any future question set.
- Confidence: high
