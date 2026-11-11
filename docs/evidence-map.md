# Evidence map: research, synthesis and evaluation

Use this map to inspect four parts of the work: how sources and evidence limits are handled, how findings are
synthesized, how competing explanations are tested, and how benchmark tasks are built. Each link points to a public
artifact in this repository. The notes distinguish what a reader can verify here from evidence that remains private.

## Source checking and provenance

- [Mechanism map accepted claims](../research/synthesis/mechanism_map_accepted_claims.md) records six exploratory
  mechanism families with their evidence types, source families, confidence and unresolved questions.
- [Contradiction register](../research/synthesis/mechanism_map_contradiction_register.md) keeps source conflicts and
  access gaps visible, including the absence of a mirrored Harness B source and uncertainty between documented
  design and observed behavior.
- [Related-work comparison](../research/related-work.md) explains how the findings relate to published evaluation
  and agent research. It is a thematic comparison, not a complete bibliography with direct citations for every claim.
- [Publication and provenance rules](../workflows/governance.md) describe the checks applied before public release;
  [engineering standards](engineering-standards.md) cover third-party source and private-material boundaries.

**Public evidence boundary:** the repository lets readers inspect the source-aware summaries and their stated
limitations, but raw Harness B trajectories and some source captures are private. References beginning
`[private-source: ...]` are not public links. The 312-run study supports behavioral reconstruction from recorded
traces; it does not establish the hidden implementation of that system, and the raw records cannot be independently
replayed from this repository.

## Research synthesis

- [Deep Synthesis guide](../research/synthesis/README.md) explains the scope, questions, method, findings,
  contradictions and limitations.
- [Harness B answered questions](../research/synthesis/harness_b_answered_questions.md) contains 18 question
  families over 312 parseable runs, with evidence-strength labels, counts, counterevidence and unknowns.
- [Harness B reconstruction](../research/synthesis/harness_b_reconstruction.md) separates stable observable patterns
  from variable behavior and hidden mechanisms.
- [Mechanism map](../research/synthesis/mechanism-map.md) and [failure taxonomy](../research/synthesis/failure-taxonomy.md)
  organize recurring mechanisms and failure families across the wider source set. Their published status is
  exploratory or accepted with warnings, not decision-ready.

## Analytical reasoning

- [Five findings](../research/findings.md) states each claim with its supporting numbers and limitations.
- [Failure study across boards](../research/core/CORE_FAILURE_STUDY_ALL_BOARDS_20261015.md) analyzes 221 runs across
  nine development tasks, separates model-specific from shared failure patterns, records corrections and errata,
  and notes that repeated runs are not independent.
- [Research-question self-audit](../research/core/CORE_SELF_AUDIT_RESEARCH_QUESTIONS_20261017.md) identifies gaps in
  the evidence and proposes how to separate model, harness, task and measurement explanations.
- [Audit that overturned a headline win](../workflows/case-studies/audit-overturned-a-win.md) traces a reported
  78.5% result to provider errors and grader rescues, then reclassifies it.
- [Held-out falsifier case study](../workflows/case-studies/falsifier-fired.md) records a pre-stated prediction that
  failed its own bar, with sample-size and timeout caveats.

## Benchmark creation and evaluation

- [Current evaluation suite](../evals/README.md) describes 28 task definitions across nine target areas, the task
  contract and grader structure, and the documented validation methods. [The catalogue](../evals/catalogue.md)
  lists 151 historical evaluation records; these are not 151 equivalent benchmark tasks or wins.
- [Known-bad and careless-agent method](../evals/methods/known-bads-and-careless-agents.md) explains the negative
  controls and solvability checks used to challenge graders.
- [Pre-registration and sentinels](../evals/methods/preregistration-and-sentinels.md),
  [held-out evaluation](../evals/methods/held-out-evaluation.md),
  [measurement validity](../evals/methods/measurement-validity.md) and
  [row-level audit](../evals/methods/row-level-audit.md) document the comparison and scoring rules, including where
  they have failed or remain incomplete.
- [Example task contract](../evals/orchestration/tasks/subagent_handoff_contract/task.yaml),
  [grader](../evals/orchestration/tasks/subagent_handoff_contract/grader/grade.py),
  [known-bad controls](../evals/orchestration/tasks/subagent_handoff_contract/known_bad/) and
  [careless-agent controls](../evals/orchestration/tasks/subagent_handoff_contract/careless/) show one concrete
  task package and its failure controls.

**Validation caveat:** the repository documents grader controls and includes a `validate-graders` command, but
[the measurement-validity record](../evals/methods/measurement-validity.md) says a fresh suite-wide run was not
recorded in that snapshot. The command checks the reference, untouched workspace, known-bad states, determinism and
Python-level grader file access; it does not execute the careless-agent scripts. It recursively discovers each
`task.yaml` under the selected root ([discovery code](../harness_evals/task.py)), so pointing it at `evals/` also
includes archived tasks. Treat the existence of the command and fixtures as method/tooling evidence; it is not by itself evidence
that every current task passed a fresh suite-wide validation. A fresh Python 3.11 check on 11 November 2026 of the
example task linked above passed 1/1 task and rejected all eight known-bad controls; the reproducible command is
`python3.11 -m harness_evals validate-graders evals/orchestration/tasks/subagent_handoff_contract`. That result
covers only the example package.
