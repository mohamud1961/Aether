# Aether-2 Hour-0 Contracts

This file freezes the implementation contracts workers should follow before wider lane work.

## 1. Observation Envelope

Worker-facing rule:
- Implement `ObservationEnvelope` exactly with the field names below.
- Do not add Aether-2-specific convenience fields.
- Do not remove fields, rename fields, or shift semantics.

```python
@dataclass
class ObservationEnvelope:
    tool: str
    exit_code: int | None
    duration_sec: float
    cwd: str
    stdout_head: str
    stdout_tail: str
    stderr_head: str
    stderr_tail: str
    truncated: bool
    raw_log_path: str
    files_changed: list[FileDelta]
    process_delta: ProcessDelta
    blind_retry_blocked: bool
    error: ErrorInfo | None
```

Semantic notes:
- Head/tail bounds are 2KB head + 2KB tail independently for stdout and stderr.
- `truncated=True` only when bounded output omits content.
- Raw output must be stored uncapped on disk and exposed only as `raw_log_path`.
- CR-rewrite and ANSI noise must collapse before head/tail extraction.
- `files_changed` is the incremental delta since the previous step.
- `blind_retry_blocked` is a truthful refusal flag, not fake replay.

## 2. Exact Tool Surface

There are exactly 10 model-visible tools, with exactly these names:

1. `run_command`
2. `start_job`
3. `job_status`
4. `session_start`
5. `session_send`
6. `session_read`
7. `read_file`
8. `write_file`
9. `wait`
10. `task_done`

Worker-facing schema rules:
- Use native provider function-calling schemas, not strict JSON-in-text prompts.
- Do not add retrieval tools, planner tools, or receipt/meta tools.
- Do not expose `search_receipts`, `view_receipt`, `view_file_cache`, `search_files`, or `probe_service`.
- `tools.py` must contain exactly these 10 schemas and no extra callable tools.

Signature freeze:

```python
run_command(cmd: str, timeout_sec: int = 120, cwd: str | None = None)
start_job(cmd: str, job_id: str | None = None, cwd: str | None = None)
job_status(job_id: str)
session_start(session_id: str, command: str)
session_send(session_id: str, keys: str)
session_read(session_id: str)
read_file(path: str, offset: int | None = None, limit: int | None = None)
write_file(path: str, content: str)
wait(seconds: int, reason: str)
task_done(summary: str, checks: list[str])
```

## 3. Loop ↔ Harbor Bridge Interface

Loop contract:

```python
def run_aether2_loop(task: TaskSpec, model_client, executor, *, deadline_ts: float) -> RunResult
```

Bridge contract:

```python
def run_task_via_harbor(task_dir: Path, loop_fn, *, deadline_ts: float) -> RunResult
```

Bridge expectations:
- The bridge mounts any loop compatible with the loop signature above.
- The bridge propagates the wall-clock deadline into the loop.
- Post-run artifact sync-back is mandatory.
- Incomplete sync-back must raise loudly, not silently degrade.

## 4. Worker Design Boundaries

- Build new code in `runner/aether2/`.
- Harvest from old code, do not redesign the architecture.
- Do not edit harvest-only files.
- Do not introduce benchmark-specific task knowledge.
- Do not add harness-side planning, phase gating, completion vetoes, or meta-tool loops.
