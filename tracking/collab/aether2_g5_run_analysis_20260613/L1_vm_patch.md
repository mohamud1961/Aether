# L1 VM Patch Spec — Launch Integrity + Measurement Fidelity

**Scope:** Phase L1 of `G5_EXECUTION_PLAN.md`. This file is a **ready-to-apply
patch/spec for the VM**, since `tools/run_aether2_g3_official.py` is VM-only
and does not exist in this local repo (it is not tracked, confirmed by
`find` in this repo turning up only the frozen
`tracking/collab/vm_pulls/.../source_snapshot/tools/run_aether2_g3_official.py`
copy). Apply this patch to the VM's working copy of
`tools/run_aether2_g3_official.py` before any further tournament runs.

**No `runner/aether2/*.py` behavior changes.** This patch only touches the
VM-only entrypoint, launcher scripts, and grader/runner-test mounting.

---

## L1-A — sys.path bootstrap (the F1 fix)

### Diagnosis recap
457/482 attempts in the frozen G4 n=2 tournament crashed with:

```
File ".../tools/run_aether2_g3_official.py", line 30, in <module>
    from runner.aether2.bridge_harbor import TaskSpec, _build_model_client
ModuleNotFoundError: No module named 'runner'
```

`source_snapshot/tools/run_aether2_g3_official.py` lines 15-32:

```python
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from runner.aether2.bridge_harbor import TaskSpec, _build_model_client
from runner.aether2.executor import ContainerBackend, ContainerExecutor
from runner.aether2.loop import run_aether2_loop
```

Lines 15-28 are stdlib-only; lines 30-32 import `runner.aether2.*` at module
top with **no `sys.path` bootstrap**. `tools/run_aether2_g2.py:34-39` (this
repo, verified present and correct) has the canonical pattern:

```python
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from runner.aether2.bridge_harbor import TaskSpec, _build_runtime  # noqa: E402
from runner.aether2.loop import run_aether2_loop  # noqa: E402
from runner.aether2.metrics import build_scorecard  # noqa: E402
```

`tools/run_benchmark_adapter_smoke.py`, `tools/run_benchmark_adapter_bfcl_native_smoke.py`,
and `tools/run_final_harness_eval_suite_baseline.py` all use the same
`REPO_ROOT` + `sys.path.insert(0, str(REPO_ROOT))` + `# noqa: E402` pattern
before any `from runner...` import — `run_aether2_g3_official.py` is the
**single outlier**.

### Exact diff to apply on the VM

Apply this unified diff to the VM's `tools/run_aether2_g3_official.py`
(adjust line numbers if the VM copy has drifted from the frozen snapshot;
the key constraint is: the bootstrap must execute **before** the first
`from runner...` import):

```diff
--- a/tools/run_aether2_g3_official.py
+++ b/tools/run_aether2_g3_official.py
@@ -25,9 +25,12 @@
 from pathlib import Path
 from typing import Any

-from runner.aether2.bridge_harbor import TaskSpec, _build_model_client
-from runner.aether2.executor import ContainerBackend, ContainerExecutor
-from runner.aether2.loop import run_aether2_loop
+REPO_ROOT = Path(__file__).resolve().parents[1]
+if str(REPO_ROOT) not in sys.path:
+    sys.path.insert(0, str(REPO_ROOT))
+
+from runner.aether2.bridge_harbor import TaskSpec, _build_model_client  # noqa: E402
+from runner.aether2.executor import ContainerBackend, ContainerExecutor  # noqa: E402
+from runner.aether2.loop import run_aether2_loop  # noqa: E402
```

This is the **minimal 1-block change** (2 new lines + 3 `# noqa: E402`
annotations on the existing import lines, matching the style of
`tools/run_benchmark_adapter_smoke.py:14-18`). It:
- adds `REPO_ROOT = Path(__file__).resolve().parents[1]` (parents[1] of
  `tools/run_aether2_g3_official.py` is the repo root, same as
  `run_aether2_g2.py`);
- inserts it onto `sys.path` (idempotent guard, matching
  `run_benchmark_adapter_smoke.py` style) **before** the `runner.aether2`
  imports;
- requires **no other code changes** — `Path` and `sys` are already imported
  (lines 24, 27 of the original).

### Validation that this kills F1
- **Known-bad (pre-patch):** `cd /tmp && env -u PYTHONPATH python3
  /home/azureuser/harnesseng_aether2/tools/run_aether2_g3_official.py --help`
  reproduces `ModuleNotFoundError: No module named 'runner'` immediately
  (rc=1, <1s, no argparse usage printed — the import fails before
  `argparse.ArgumentParser()` is even constructed).
- **Post-patch:** the same command must print argparse usage (or fail later,
  e.g. on `--task-id` being required) — **not** the `ModuleNotFoundError`.
  This is exactly what `tests/test_aether2_entrypoint_import_hygiene.py`
  (this repo) checks generically for every `tools/run_aether2_*.py`; once
  `run_aether2_g3_official.py` exists on the VM with this patch applied, that
  same test file can be copied/run on the VM to confirm.

---

## L1-B — hardened launcher

Implemented in this repo as `scripts/run_aether2_tournament.sh`
(executable, `--help`/`--dry-run` supported). Summary of what it does (full
behavior documented in its own `--help`):

1. `export PYTHONPATH=<repo-root>` for every child process.
2. **Preflight import check** — `python3 -c "import
   runner.aether2.bridge_harbor"` under that `PYTHONPATH`; aborts with exit
   code `2` (no corpus touched) if it fails.
3. Per-task loop over `--task-ids-file` (one task id per line, same shape as
   the frozen `task_ids.txt`), invoking
   `tools/run_aether2_g3_official.py --task-id ... --task-root ...
   --output-root ... --agent-timeout-sec ... --test-timeout-sec ...` under
   `timeout --foreground <per-task-timeout-sec>`, recording
   `attempt\ttask_id\trc\telapsed\ttimestamp` to `<output-root>/progress.tsv`
   (same schema as the frozen `resume_full_twice.sh`).
4. **Fail-fast guard** — if `--fail-fast-count` (default 5) consecutive task
   launches return `rc!=0` with `elapsed<=--fail-fast-elapsed-sec` (default
   2s), abort with exit code `3` instead of marching through the remaining
   corpus. This is exactly the F1 signature (`rc=1`, `elapsed<=2s`,
   byte-identical traceback).
5. **`invalid_launch` marker rows** — after each task, search
   `<output-root>/*/<task_id>/row.json` (the entrypoint creates its own
   `<output-root>/<UTC-timestamp>/<task_id>/` subdir per invocation per
   `source_snapshot/tools/run_aether2_g3_official.py:78-79,109`). If no
   `row.json` is found for that task, append
   `attempt\ttask_id\trc\telapsed\tinvalid_launch\ttimestamp` to
   `<output-root>/invalid_launches.tsv`. This guarantees every attempted task
   produces a truthful row even when the grader was never reached (covers
   F1-style import crashes, F7-style SIGTERM/timeout kills before `row.json`
   is written, and any other silent-`rc=1` case).

### Usage on the VM (after L1-A is applied)

```bash
cd /home/azureuser/harnesseng_aether2

# 1. preflight only (no corpus needed)
scripts/run_aether2_tournament.sh --dry-run

# 2. micro-smoke (3 tasks) -- see "VM execution handoff" below
printf '%s\n' hello-world acl-permissions-inheritance break-filter-js-from-html \
  > /tmp/micro_smoke_task_ids.txt
scripts/run_aether2_tournament.sh \
  --task-ids-file /tmp/micro_smoke_task_ids.txt \
  --task-root /home/azureuser/terminal-bench-official/original-tasks \
  --output-root /home/azureuser/aether2_full_tournament/l1_micro_smoke_$(date -u +%Y%m%dT%H%M%SZ) \
  --attempt 1
```

---

## L1-C — measurement-fidelity checklist (VM-runner side)

These items all touch `tools/run_aether2_g3_official.py` and/or the VM task
mount/grader setup, not `runner/aether2/`. They are specified here as a
checklist for the VM agent; none require a local code change beyond L1-A.

- [ ] **Mirror official test mount at both `/tests` and the runner path.**
  `source_snapshot/tools/run_aether2_g3_official.py` copies official tests
  into the container only after the agent run (per its docstring: "only
  copies official tests into the container after the agent run"). Confirm
  the copy target matches **both**:
  - the path the official `run-tests.sh` expects (typically `/tests` per
    TerminalBench convention), **and**
  - whatever path the Aether-2 runner/grader step actually reads from
    (check `copy_tests`/`copied_tests`/`copied_runner` helpers around
    `source_snapshot/tools/run_aether2_g3_official.py:353-367`).
  If these two paths diverge, `break-filter-js-from-html` (a known mount-fidelity
  sentinel per `failure_taxonomy.md` F1 note / `g5_lane_recommendation.md`)
  and similar tasks will fail the grader step even when the agent's work is
  correct. Fix: mount/copy tests to both locations (symlink or dual-copy),
  not a `runner/aether2/` change.

- [ ] **Hermetic grader toolchain.** The grader (`run-tests.sh` /
  `aether2-run-tests.sh`) must bring its own `pytest`/`uv` (e.g. a
  pre-baked venv or vendored binary copied into the container alongside the
  tests), so that a deliberately-or-accidentally broken agent environment
  (F5: `broken-networking`, `broken-python` — both hit `uv`/`pytest`
  `command not found`, exit 127) cannot 127 the grade. Concretely: do not
  rely on the agent's `PATH`/venv for the grader's own interpreter; invoke
  the grader via an absolute path to a toolchain installed at container-build
  time (outside the agent's writable environment) or copied in
  read-only post-run.

- [ ] **Classify exit/return codes as `invalid_run`/`invalid_environment`,
  not capability fails.** In `tools/run_aether2_g3_official.py`'s row-writing
  logic (`row_from_failure`, the `row_status` assignment around line 270 and
  the `"invalid_environment" if "docker" in reason or ...` branch around line
  439), add these classifications:
  - `verifier_exit_code == 127` → `row_status = "invalid_run"` (grader
    toolchain missing, per F5) — **not** `"fail"`.
  - Docker `returncode == 137` (SIGKILL/OOM, per F6 `build-linux-kernel-qemu`)
    → `row_status = "invalid_environment"`.
  - Provider HTTP 400 (`ModelClientError('azure openai request failed with
    status 400')`, per F6 `add-benchmark-lm-eval-harness`) → `row_status =
    "invalid_environment"` (rejected request, not a capability fail).
  These three reason codes should **not** count toward pass-rate denominators
  (AGENTS.md: "any attempt that does not reach the grader is emitted as an
  explicit `invalid_launch`/`invalid_environment` row and excluded from
  pass-rate denominators — never silently counted as a capability fail").
  Note: 127/137/400 *do* reach far enough to produce a row — they are
  distinguished from F1/F7 (which produce no row at all, handled by
  `invalid_launches.tsv` in L1-B) by still writing `row.json` with the
  `invalid_run`/`invalid_environment` `row_status`.

- [ ] **Phase-boundary `row.json` on timeout/kill.** F7
  (`build-initramfs-qemu`, SIGTERM at 2739s, 0-byte log, no `row.json`) means
  a killed task leaves **zero** evidence. Add a best-effort `row.json` write
  at each phase boundary (before agent run starts, after agent run completes,
  before/after grader run) with a partial row (`row_status:
  "in_progress"`/`"invalid_run"`, `phase: "agent_run" | "test_run"`,
  `started_at`, timestamps) so that if the process is SIGTERM'd mid-phase,
  the **last-written partial `row.json`** survives and shows which phase was
  reached. Combined with L1-B's `invalid_launches.tsv` (which fires when
  *no* `row.json` exists at all), this gives every attempted task — even
  killed ones — a truthful trace of how far it got.

None of the above require new `runner/` modules; they are localized edits to
`tools/run_aether2_g3_official.py`'s row-writing and test-mount logic. If a
small *generic* helper (e.g. a `row_status` classification function shared
between `tools/run_aether2_g3_official.py` and `tools/run_aether2_g2.py`)
becomes useful, it could live under `runner/` (not `runner/aether2/`) as a
plain utility with no task-conditional logic — but this is optional and out
of scope for the current L1 patch; the checklist above is self-contained as
inline edits to the VM-only entrypoint.

---

## VM-execution handoff

**This sandbox cannot reach the Azure control plane, Docker, or the VM.** No
tournament was (or could be) re-run from here. The steps below are staged
for a VM-side agent/operator to execute after applying L1-A above.

### Step 0 — apply L1-A and verify the preflight
```bash
cd /home/azureuser/harnesseng_aether2
git apply <<'EOF'
<paste the diff from L1-A above>
EOF

export PYTHONPATH="$(pwd)"
python3 -c "import runner.aether2.bridge_harbor" && echo "preflight OK"

# known-bad repro check (should now FAIL to reproduce the ModuleNotFoundError)
cd /tmp && env -u PYTHONPATH python3 /home/azureuser/harnesseng_aether2/tools/run_aether2_g3_official.py --help
# expect: argparse usage or a --task-id required error -- NOT
# "ModuleNotFoundError: No module named 'runner'"
cd /home/azureuser/harnesseng_aether2
```

### Step 1 — micro-smoke (3 tasks)
Tasks: a trivial task (e.g. `hello-world` or the simplest available task),
`acl-permissions-inheritance` (known pass), `break-filter-js-from-html`
(mount-fidelity sentinel).

```bash
printf '%s\n' hello-world acl-permissions-inheritance break-filter-js-from-html \
  > /tmp/l1_micro_smoke_task_ids.txt

scripts/run_aether2_tournament.sh \
  --task-ids-file /tmp/l1_micro_smoke_task_ids.txt \
  --task-root /home/azureuser/terminal-bench-official/original-tasks \
  --output-root /home/azureuser/aether2_full_tournament/l1_micro_smoke_$(date -u +%Y%m%dT%H%M%SZ) \
  --attempt 1
```

**Success checks (micro-smoke):**
- [ ] `runner.aether2.bridge_harbor` imports (preflight prints "preflight OK").
- [ ] Each task writes a `row.json` under `<output-root>/<timestamp>/<task_id>/row.json`.
- [ ] Grader actually runs (`row.json` has a non-null `verifier_exit_code`,
  or an explicit `invalid_run`/`invalid_environment` `row_status` with a
  reason — not a bare crash).
- [ ] `/tests` mount works for `break-filter-js-from-html` (no
  `FileNotFoundError`/missing-tests error in its log).
- [ ] `acl-permissions-inheritance` still passes (`row_status == "pass"`,
  `verifier_exit_code == 0`).
- [ ] No `invalid_launches.tsv` entries (or if any, they have a clear,
  non-F1 reason).

### Step 2 — targeted set (10-15 tasks)
Per `G5_EXECUTION_PLAN.md` run-cadence: the 5 known passes
(`acl-permissions-inheritance`, `analyze-access-logs`, `assign-seats`,
`attention-mil`, `build-pmars`) + measurement/fidelity failures
(`break-filter-js-from-html`, `broken-python`, `broken-networking`,
`build-stp`, `build-cython-ext`) + hard sentinels (`qemu-startup`,
`extract-moves-from-video`, `install-windows-3.11`, `video-processing`).

```bash
cat <<'EOF' > /tmp/l1_targeted_task_ids.txt
acl-permissions-inheritance
analyze-access-logs
assign-seats
attention-mil
build-pmars
break-filter-js-from-html
broken-python
broken-networking
build-stp
build-cython-ext
qemu-startup
extract-moves-from-video
install-windows-3.11
video-processing
EOF

scripts/run_aether2_tournament.sh \
  --task-ids-file /tmp/l1_targeted_task_ids.txt \
  --task-root /home/azureuser/terminal-bench-official/original-tasks \
  --output-root /home/azureuser/aether2_full_tournament/l1_targeted_$(date -u +%Y%m%dT%H%M%SZ) \
  --attempt 1
```

**Success checks (targeted set):**
- [ ] **Reach-grader rate ≥ 95%** — i.e. ≥ 13/14 tasks produce a `row.json`
  with a non-null `verifier_exit_code` or an explicit `invalid_run`/
  `invalid_environment`/`invalid_launch` classification (not a bare F1-style
  crash).
- [ ] **All 5 known passes still pass** (`acl-permissions-inheritance`,
  `analyze-access-logs`, `assign-seats`, `attention-mil`, `build-pmars`):
  `row_status == "pass"`, `verifier_exit_code == 0`. Any regression here is a
  **stop/escalate** per the plan's "Stop/kill" clause.
- [ ] `break-filter-js-from-html` — mount fidelity resolved (L1-C item 1); a
  flip to `pass` is plausible per the plan's "+1 to +2" estimate but not
  required for L1 exit.
- [ ] `broken-python`/`broken-networking` — `row_status` is now `invalid_run`
  (toolchain-missing, L1-C item 3), not silently `fail`, **if** the L1-C
  hermetic-grader item is not yet applied; or `pass`/`fail` on real grading
  if it is applied.
- [ ] `build-initramfs-qemu`-class tasks (if included in a later targeted
  run) leave a partial `row.json` on timeout/kill (L1-C item 4) even if
  killed.
- [ ] No fail-fast abort (exit code 3) — if it triggers, L1-A did not fully
  resolve F1; stop and escalate per the plan.

### What remains VM-side / not verifiable from here
- L1-A patch application and the known-bad repro check (Step 0).
- L1-C checklist items (test-mount mirroring, hermetic grader toolchain,
  127/137/400 classification, phase-boundary `row.json`) — all are edits to
  the VM-only `tools/run_aether2_g3_official.py` and the container build/mount
  setup.
- Micro-smoke and targeted-set runs (Steps 1-2) and their success checks.
- Any reach-grader-rate, pass-rate, or sentinel measurement — **all require
  the VM/Docker/model backend**, which this sandbox cannot reach.

This sandbox could not reach the Azure control plane, Docker, or the VM at
any point during this work; no VM, container, or process was started or left
running by this L1 patch-spec task.
