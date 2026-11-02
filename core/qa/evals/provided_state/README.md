# Provided-state sensor diagnostic

This is a transparent, locally generated task pack, not TerminalBench data.
The task-facing message and initial files are distinct from the grader's
expected final bytes. A scripted provider executes each fixed policy through
Core's real local tool loop; the grader then compares the resulting files to
the frozen case contract. No hidden task files or model/provider calls are
used. Full synthetic requests, traces, output files and a scored row are kept
under the evidence directory created by the runner.

There are two independent questions:

1. Does the artifact grader distinguish the fixed known-good and known-bad
   policies, including an edit required by the task?
2. Does Core truthfully make the relationship between an initial observation
   and subsequent metadata change available to the model, without claiming
   changed content or wrongdoing? If the initial observation fails, the
   relation must remain unknown.

The desired sensor contract is a record containing an initial-workspace
status and, for each observed difference, a relative path and the first
observation step. The model-facing note must identify the same relationship
as a metadata observation, with its timing, without declaring that the file
content is different or the edit is wrong. An absent initial observation is
unknown, not an empty manifest. This diagnostic requires successful artifact
controls before it interprets sensor results.

Baseline expectation, frozen before the start-linkage implementation:
commit `011a3cf7` grades good and bad artifacts correctly, but has no
structured initial-workspace change record or corresponding explicit
model-facing relationship. The known-bad is not rescued by a scripted
policy, and the good edit is not labeled wrong. The proposed minimal change
predicts that both observed edits and a same-byte touch are reported as
metadata differences, the unchanged control stays quiet, and the failed
initial probe stays unknown. This does not establish Luna's response, task
success, file-content changes, process execution, or general applicability.

Run only with a new owned evidence path:

```
uv run --offline python -m qa.evals.provided_state.run --evidence qa/evidence/provided_state_<source>
```
