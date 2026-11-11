# Deep Synthesis: research guide

This is the public reading path for Aether's cross-system research into agent harnesses: how agents plan, use tools,
verify work, recover from failure and stop. The wider synthesis covers five external source systems and 12+ failure
families. Its trace layer analyses **312 parseable runs from one external harness**, called Harness B. Those traces
support a behavioral reconstruction of what was visible in the runs; they do not reveal the harness's hidden code.

## Research questions

The trace analysis groups 18 question families around four questions:

1. **What work pattern is visible?** How do planning, executor roles, branching and handoffs appear in the traces?
2. **How does the agent work through a task?** What does it inspect, how does it use tools, and when does it replan
   or debug?
3. **How does it decide work is complete?** What does the verifier check, how often does it recover after rejection,
   and how do internal completion signals compare with final outcomes?
4. **Which observed behaviors accompany success or failure?** Where are the strongest recurring patterns, and where
   do task mix or missing visibility leave multiple explanations open?

These are descriptive questions about a particular corpus, not claims that any observed mechanism caused success.

## Method

- The trace layer is a **post-hoc analysis** of 312 parseable runs of Harness B. It answers 18 question families from
  visible events, tool calls, rendered context and recorded outcomes.
- Each answer labels its evidence strength, separating direct observations from strong inferences, partial answers and
  irrecoverable gaps. It records counterevidence and unknowns alongside the supporting observations.
- The wider synthesis compares available source, documentation, evaluation, issue and trajectory evidence across
  five systems and groups recurring patterns into mechanism families and failure families.
- The mechanism map and failure taxonomy retain disagreements in a contradiction register instead of averaging them
  into a single story. The full method for Aether's own experiments is documented in
  [evaluation methods](../../evals/README.md); that experimental method should not be confused with this post-hoc
  external-trace study.

## Key findings

| Finding | Evidence | What it supports |
|---|---|---|
| Planner activity precedes executor activity in all 312 parseable runs. | [Answered questions](harness_b_answered_questions.md) | A stable **observable** role pattern in this corpus; not proof of hidden scheduler implementation. |
| 297 of 312 runs replan at least once. | [Answered questions](harness_b_answered_questions.md) | Replanning is common in the visible traces; its benefit is not isolated. |
| A verifier appears in 272 of 312 runs. Runs with a verifier have a higher recorded success share (0.908 vs. 0.2 without one). | [Answered questions](harness_b_answered_questions.md) | An association only: task difficulty and task type are not normalized, so this is not a causal estimate. |
| Seventeen runs show a verifier pass and still fail overall. | [Answered questions](harness_b_answered_questions.md) | Internal verifier status and final task acceptance are different signals. |
| Multiple-executor runs have a lower observed success rate than single-executor runs (0.724 vs. 0.878). | [Answered questions](harness_b_answered_questions.md) | A pattern that may reflect harder tasks being assigned more executors; it does not show that branching hurts. |

The [harness reconstruction](harness_b_reconstruction.md) summarizes the recurring patterns and separates them from
variable behavior and hidden implementation details.

## Contradictions kept open

- **Behavior versus implementation:** planner/executor/verifier separation is strongly visible in Harness B traces,
  but there is no mirrored source for that system. The result remains a behavioral reconstruction.
- **Verifier status versus final outcome:** some runs pass the internal verifier but fail the overall evaluation.
  Neither signal can stand in for the other.
- **Branching versus success:** multi-executor runs succeed less often in this corpus, while task difficulty may drive
  both executor count and failure.
- **Documented design versus implementation:** the synthesis records tension between sandbox language and a local
  shell backend in DeepAgents, and uncertainty about whether KIRA's weaker visible verifier pattern is a real system
  difference or a trace-rendering effect.

The [contradiction register](mechanism_map_contradiction_register.md) records these tensions, their evidence paths and
their status. The [accepted-claims file](mechanism_map_accepted_claims.md) preserves support types and confidence for
the mechanism claims.

## Limitations and access boundary

- The 312-run cohort is from one external harness and consists of parseable runs. It is not a representative sample
  of all agents or tasks.
- The analysis is post-hoc and observational. Task difficulty, task type and tool choice are confounded; correlations
  do not establish causes.
- Rendered traces do not expose hidden scheduling, prompt assembly, branch cancellation or every internal decision.
  A visible role pattern cannot establish how the system implemented it.
- The raw Harness B traces and some source captures are private and are not included in this public repository.
  References marked `[private-source: ...]` identify evidence that a public reader cannot open here. The published
  files let readers inspect the analysis and its stated limits, but not independently replay every underlying record.
- The synthesis status pages are dated snapshots. The mechanism map is dated 4 April 2026 and marks Wave 01 as an
  exploratory, incomplete anchor. The failure taxonomy is dated 11 April 2026: Waves 01–03 are accepted with
  warnings, Wave 04 is open, and no family is marked decision-ready.

## Reading path

| File | What it contains |
|---|---|
| [Mechanism map](mechanism-map.md) | Six Wave 01 exploratory mechanism families, interaction structure and scope limits |
| [Failure taxonomy](failure-taxonomy.md) | Failure families, carried contradictions, coverage frontier and saturation status |
| [Accepted mechanism claims](mechanism_map_accepted_claims.md) | Claim-level support types and confidence labels |
| [Contradiction register](mechanism_map_contradiction_register.md) | Open conflicts and evidence gaps |
| [Harness B answered questions](harness_b_answered_questions.md) | Eighteen trace-question families, counts, confidence, counterevidence and unknowns |
| [Harness B reconstruction](harness_b_reconstruction.md) | Stable observable patterns, variable behavior and hidden-mechanism boundary |
| [Informal cluster dossiers](informal_cluster_dossiers/README.md) | Cross-corpus operator and issue evidence by failure cluster |
| [Evaluation dossiers](eval_dossiers/README.md) | Benchmark, task and verifier evidence relevant to the failure families |

For Aether's own experimental findings, see [research findings](../findings.md), the
[related-work comparison](../related-work.md), and [evaluation design](../../evals/README.md). Case studies of
trajectory audits are in [workflows/case-studies](../../workflows/case-studies/).
