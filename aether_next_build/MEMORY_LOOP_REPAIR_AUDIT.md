# Memory Loop Repair Audit

Date: 2026-06-30

## Purpose

Repair the SPARQL-style failure mode found in the Phase 1-6 audit:

- solver called `query_memory` at step 0 even on a fresh task;
- repeated `query_memory` calls reused the same action id (`a1`), so receipts like `a1:query` could be de-duplicated by the ledger;
- after a primary file read, context showed `files_already_read` but did not preserve enough latest read evidence/excerpt for the solver to act;
- prior `query_memory` receipts could be returned as search hits, creating self-referential memory loops;
- architect/stable solver guidance over-biased the solver toward memory-first behaviour.

## Changes Implemented

### 1. Step-scoped action receipt ids

Action-generated receipts now include the step number, e.g.

```text
step-0:a1:query
step-1:a1:query
step-0:r1:read
step-0:w1:write
```

This prevents ledger de-duplication from silently dropping repeated action ids across turns.

Updated areas:

- `aether_next/kernel_actions.py`
- `aether_next/kernel.py`
- `aether_next/execution.py`
- `run_check` receipt prefixing

### 2. `query_memory` no-new-evidence feedback

`query_memory` receipts now record:

```json
{
  "no_new_evidence": true,
  "guidance": "query_memory returned no new evidence... do not repeat the same memory query"
}
```

when the query has no hits or repeats the same result set.

### 3. Query-memory self-reference guard

`query_memory` no longer returns previous `query_memory` receipts as normal task evidence by default.

They are searchable only if explicitly filtered with `event_type`/`kind` containing `query_memory`.

This prevents a prior empty memory query from becoming the only “hit” for the next identical query.

### 4. Latest file-read evidence preserved in context

Context packets now include `latest_file_reads` when successful reads exist:

```json
{
  "path": "university_graph.ttl",
  "content_hash": "...",
  "bytes": 10169,
  "excerpt": "..."
}
```

This fixes the broken middle state where context told the solver “you already read this file” without showing what was read.

### 5. Memory-loop feedback in context

After repeated empty/no-new-evidence memory queries, context includes:

```json
{
  "memory_loop_feedback": {
    "guidance": "Repeated query_memory calls produced no new evidence. Act on existing file/check evidence..."
  }
}
```

### 6. Prompt/manual guidance changed

Stable solver and architect guidance now says:

- do not call `query_memory` as a mandatory first action on a fresh task;
- inspect primary task files directly first;
- use `query_memory` before repeats, reruns, overwrites, or when retrieving prior evidence.

Updated areas:

- `aether_next/model_hooks.py`
- `aether_next/compiler.py`
- `aether_next/context_compiler.py`
- `aether_next/workbench_hooks.py`
- `aether_next/runtime_manual.py`
- `aether_next/run_adapter.py`
- `aether_next/integration_scenarios.py`

## Tests Added

Added `tests/test_memory_loop_fixes.py` covering:

1. repeated action ids now produce unique `query_memory` receipts;
2. repeated/no-result memory queries produce explicit no-new-evidence guidance;
3. context surfaces `memory_loop_feedback` after repeated empty memory calls;
4. latest file read excerpts are preserved in context;
5. `query_memory` can retrieve the previous file-read excerpt by path/query.

Updated existing tests to account for step-scoped receipt ids and `latest_file_reads` being a standard context section.

## Validation

```text
python3 -m pytest -q tests/test_memory_loop_fixes.py
3 passed
```

```text
python3 -m pytest -q tests/test_memory_loop_fixes.py tests/test_chatgpt_broad_slice.py tests/test_chatgpt_integration_scenarios.py tests/test_vnext_memory_context_verifier.py
48 passed
```

```text
python3 -m pytest -q --ignore=tests/test_docker_runner.py
195 passed
```

```text
python3 -m compileall -q aether_next
passed
```

```text
python3 run_verifier_only_eval.py --mode fake --out-dir /mnt/data/memory_fix_fake
python3 validate_verifier_only_eval.py /mnt/data/memory_fix_fake --report /mnt/data/memory_fix_fake_validation.md
ok=true
```

## Remaining Caveats

- This is deterministic repair only. It has not rerun the real SPARQL task with model solver.
- It does not guarantee the solver will write `solution.sparql`, but it removes the concrete memory-loop causes found in the trace.
- The next validation should rerun the same three narrow tasks with a larger step cap and confirm whether SPARQL now acts after reading the TTL instead of looping on memory.

## Next Recommended Codex Step

Rerun only the three narrow tasks after integrating this slice:

- `filter-js-from-html`
- `sparql-university`
- `openssl-selfsigned-cert`

Recommended config for this rerun:

```text
max_steps: 24-30
run_timeout_s: higher than 30s
```

Audit specifically:

- Does SPARQL still call `query_memory` at step 0?
- After reading `university_graph.ttl`, does context show `latest_file_reads` with excerpt?
- If repeated `query_memory` happens, does `memory_loop_feedback` appear?
- Does the solver write `solution.sparql`?
- Does verifier get called on submit/failure/no-progress candidate?
