# Ledger entry (RAW_LEDGER_UPDATE)

Write one entry for each material result, decision, failure, or implementation change. The entry is raw input to the historian. It is not the final ledger record. Keep it factual and short. Separate observation from inference. Keep negative results.

```text
RAW_LEDGER_UPDATE
- actor: <agent or principal>
- task: <task name, plain>
- event_type: decision | experiment | failure | source_analysis | implementation | regression | open_question
- summary: <one or two sentences, the result in plain words>
- observations: <direct facts only, each with its evidence path>
- inference: <interpretation, labelled as such>
- evidence_paths:
  - <path>
- affected_components: <list>
- decision_change: <what changed because of this, or "none">
- unresolved_questions: <list, or "none">
- confidence: high | medium | low, with the reason
- commit_message: <imperative subject that matches the staged diff, or HOLD - <reason>, or NONE - no tracked file changes>
```

## Rules

- A failed prediction is recorded as failed. Do not reword it as a partial win.
- Invalid rows are recorded with their class and kept in the record.
- Every number has an evidence path.
- If the entry is not ready to commit, use `HOLD - <reason>`.
