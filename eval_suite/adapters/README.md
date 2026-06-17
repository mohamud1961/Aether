# Adapters

Benchmark adapter code is **not redistributed in this public tree** for two reasons:

1. **Licensing** — the benchmark corpora (question sets, answer keys, evaluation
   scripts) are each governed by their own licenses. Redistributing adapter code
   that is tightly coupled to a corpus would require redistributing the corpus
   itself, or at minimum making implied license claims we cannot make.

2. **Import coupling** — each adapter in the original runtime imports from 5–6
   other `runner.*` modules (asset loaders, measurement contracts, grading
   contracts, schema validators). Extracting them without their full dependency
   chain would produce non-runnable stubs.

## What adapters do

Each adapter bridges one external benchmark family into the harness runner loop.
The adapter provides:

- a `load_rows(fixture_root)` function that yields `EvalRow` objects
- a `grade_row(row, candidate_output)` function that returns a `GradeResult`
- family-level metadata (failure cluster labels, surface type, authority label)

The adapter contract is defined in `runner/benchmark_adapter_contracts.py`
(not redistributed here) and mirrors the `EvalSubstrateContracts` schema.

## Where the real graders live

For the **task-pack families** (families/<mechanism-family>/<pack>/), the
grader lives inside the task pack itself at `<pack>/grader/grade.py`. These
are self-contained Python scripts that take `--candidate`, `--trace`, and
`--output` arguments and emit a `GradeResult` JSON. No adapter is needed to
run them.

For adapter-driven lanes (external benchmark families integrated via the
runner loop), the adapter code resides in `runner/` and is not included here.

## Neutral family names

The adapter-driven lanes are documented under neutral mechanism-cluster names:

| neutral name            | mechanism cluster     |
|-------------------------|-----------------------|
| tool_call_composite     | tooling/tool-call     |
| tool_call_atom          | tooling/tool-call     |
| retrieval_reduction     | retrieval/reduction   |
| filesystem_agent        | filesystem/path       |
| terminal_task           | filesystem/path       |
