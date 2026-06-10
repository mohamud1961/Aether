# Run And VM Operations

Use this skill when a loop needs to start, monitor, or close out a long-running
run on a local container, background process, or remote VM.

The skill turns run operations into a controlled lease: why the environment is
needed, what command is running, where evidence lands, who owns shutdown, and
what happens if the run becomes invalid.

## Governing Question

Can the run execute in the right environment, produce auditable artifacts, and
leave no unreported external state behind?

## Use Cases

- Start a calibration or eval run that needs Linux/container conditions.
- Run a tournament or multi-candidate score job.
- Monitor a background runner while another thread analyzes results.
- Collect artifacts from a VM or container after a failure.
- Stop or deallocate a VM once no active job needs it.
- Convert an invalid run into a useful environment failure report.

## Lease Contract

Before launch, write down:

- owner thread;
- purpose of the run;
- backend: local process, container, VM, or cloud VM;
- expected command, cwd, env, and output root;
- max runtime or budget;
- artifact paths;
- monitor cadence;
- teardown rule;
- handoff recipient.

## Workflow

1. **Preflight**
   - Confirm the backend exists and credentials are available without exposing
     secrets.
   - Confirm disk, Python/runtime, container/VM status, and expected cwd.
   - Confirm no stale process is using the same run id or output path.

2. **Launch**
   - Use a unique run id.
   - Capture command, cwd, env summary, start time, and output root.
   - Prefer a log file or receipt directory over terminal-only output.

3. **Monitor**
   - Check heartbeat, logs, artifact growth, and timeout/budget.
   - Classify failures as environment, provider, tool contract, grader,
     timeout, or unclear before retrying.
   - Do not relaunch blindly after the same invalid condition repeats.

4. **Collect**
   - Capture stdout/stderr, result rows, scoreboards, traces, manifests,
     config snapshots, and verifier output where applicable.
   - Record missing artifacts as evidence, not as silence.

5. **Teardown**
   - Stop local processes that the loop started.
   - Stop or deallocate VM resources when no active job needs them.
   - If the current environment cannot perform teardown, record the exact
     manual command or owner action required.

6. **Handoff**
   - Return run status, artifact paths, failure classification, and external
     state to the orchestrator.

## Output Contract

```text
run_id:
backend:
owner:
command:
cwd:
output_root:
start_time:
end_time:
status: complete | partial | invalid_due_to_environment | blocked
artifact_paths:
failure_class:
teardown_status:
external_state_remaining:
next_action:
```

## Guardrails

- Never hide a running process, server, container, or VM in a handoff.
- Never count an invalid environment row as capability evidence.
- Never rerun a costly job without naming what new evidence the rerun will add.
- Prefer one decisive diagnostic over a broad rerun when failure class is
  unclear.

