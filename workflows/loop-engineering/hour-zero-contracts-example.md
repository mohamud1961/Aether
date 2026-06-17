# Hour-Zero Contracts — Example

This is a sanitized example of the contract-freeze discipline used before
worker dispatch began on the Aether-2 build. Model version strings and
internal references have been replaced with generic terms.

The Hour-0 pattern: before any worker receives a packet, the orchestrator
freezes the interface contracts that workers build against. This prevents
workers from making incompatible assumptions and eliminates integration
rework from interface drift.

---

## Why Hour-0 Contracts Exist

Interface drift is the main integration risk in a parallel multi-worker build.
If Worker A builds against one assumption about the envelope schema and Worker B
builds against another, the integration step creates rework.

The fix: freeze the contracts before dispatch. Workers build against the frozen
spec, not against each other's outputs or against guesses.

---

## What Gets Frozen at Hour-0

The orchestrator identifies the smallest set of interface contracts that, if left
unfrozen, would create worker-to-worker dependency conflicts. Everything else can
be resolved worker-locally.

For the Aether-2 build, three surfaces were frozen:

1. The observation envelope schema
2. The exact tool surface (names, signatures, count)
3. The loop ↔ bridge interface

---

## 1. Observation Envelope Contract

**Worker-facing rule:** implement the observation envelope exactly with the fields
below. Do not add convenience fields. Do not remove fields, rename fields, or shift
semantics.

```
ObservationEnvelope:
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
- Head/tail bounds: 2 KB head + 2 KB tail independently for stdout and stderr.
- `truncated=True` only when bounded output omits content.
- Raw output must be stored uncapped on disk and exposed only as `raw_log_path`.
- CR-rewrite and ANSI noise must collapse before head/tail extraction.
- `files_changed` is the incremental delta since the previous step.
- `blind_retry_blocked` is a truthful refusal flag, not fake replay.

---

## 2. Exact Tool Surface Contract

**Worker-facing rule:** there are exactly 10 model-visible tools, with exactly
these names:

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

Schema rules:
- Use native provider function-calling schemas, not strict JSON-in-text prompts.
- Do not add retrieval tools, planner tools, or receipt/meta tools.
- The tools module must contain exactly these 10 schemas and no extra callable tools.

Signature freeze:

```
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

---

## 3. Loop ↔ Bridge Interface Contract

Loop contract:

```
def run_loop(task: TaskSpec, model_client, executor, *, deadline_ts: float) -> RunResult
```

Bridge contract:

```
def run_task_via_bridge(task_dir: Path, loop_fn, *, deadline_ts: float) -> RunResult
```

Bridge expectations:
- The bridge mounts any loop compatible with the loop signature above.
- The bridge propagates the wall-clock deadline into the loop.
- Post-run artifact sync-back is mandatory.
- Incomplete sync-back must raise loudly, not silently degrade.

---

## 4. Worker Design Boundaries

- Build new code in the designated new harness directory.
- Harvest from old code; do not redesign the architecture.
- Do not edit harvest-only files.
- Do not introduce task-specific knowledge into the harness.
- Do not add harness-side planning, phase gating, completion vetoes, or meta-tool loops.

---

## Lessons from This Example

**What worked:**

- Freezing the envelope schema before dispatch eliminated the main integration
  risk. Workers built against the same field contract without coordination.
- The tool-count constraint (exactly 10, named) prevented scope creep. Workers
  could not silently add convenience tools.
- The bridge interface contract was the right level of abstraction: it specified
  the interaction contract without over-specifying internal implementation.

**What we learned during the build:**

- The contract-complete packet requirement (added as D-011 mid-build) should be
  a pre-dispatch rule, not a retrospective one. Earlier workers received thinner
  packets and needed follow-up re-dispatch.
- Interface contracts at Hour-0 are necessary but not sufficient. The
  **component contracts** (the full behavioral spec for each module) also need to
  be complete before dispatch, not just the cross-module interfaces.

---

*Private content removed: model version strings, internal script names, VM
references. The contract-freeze pattern and semantic notes are public artifacts.*
