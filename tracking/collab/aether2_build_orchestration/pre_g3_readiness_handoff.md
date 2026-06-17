# Aether-2 Pre-G3 Readiness Handoff

- Date: 2026-06-12
- Actor: Aether-2 Pre-G3 Stabilization owner
- Goal objective: `Stabilize Aether-2 through genuinely green G1 and G2 gates, complete a real clean Codex Review over the resulting dirty tree, and produce one authoritative G1/G2 closeout that makes the repository ready to begin G3.`
- Review gate originally requested: `codex_review_skill_plus_adversarial`
- Current status: `PARTIAL_COMPLETE_G2_CONTAINER_AND_PROCESS_PRESSURE_BLOCKED`

## Authority

This is the single current G1/G2 truth for the live tree.

Historical notes remain in:
- [g1_checkpoint_handoff.md](/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_build_orchestration/g1_checkpoint_handoff.md)
- [pre_g1_completion_handoff.md](/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_build_orchestration/pre_g1_completion_handoff.md)

Those files are evidence only. This file supersedes their old G2 claims.

## Executive summary

What is complete:
- Detached-job exit correctness remains fixed in the live tree, and the named regression still passes.
- The `g2_03` false-positive hole is repaired in code:
  - `tools/run_aether2_g2.py` now emits a harness-authored verifier context outside the model workspace.
  - `tracking/collab/aether2_g2_homologs/g2_03_interactive_session/verifier.sh` now requires real session-tool evidence plus `session_survival=true`, not just `result.txt == 42`.
  - Container-backed G2 runtime wiring is enabled through the existing Aether docker backend, with local-image build fallback when a homolog has `task.toml` + `Dockerfile`.
  - Container-backed runtime failures are now reported as `invalid_environment` instead of crashing the whole board.
- Fresh focused G1 rerun after these changes is green.
- Compile and genericity checks are green.

What is not complete:
- G2 is not green.
- A required tmux-capable container rerun could not be completed because Docker daemon is unavailable on this host.
- The host is still under severe fork/process pressure, and that pressure contaminated verifier execution for other G2 rows.

Because of those blockers, the repository is **not** `READY_TO_BEGIN_G3`.

## 1. Detached job exit correctness

Command:

```bash
python3 -m pytest tests/test_aether2_jobs.py::test_job_registry_persists_and_reports_real_exit_code -q -p no:cacheprovider
```

Result:
- `1 passed in 0.51s`

Evidence:
- [tests/test_aether2_jobs.py](/Users/mohamud/Downloads/harnesseng/tests/test_aether2_jobs.py)
- [jobs.py](/Users/mohamud/Downloads/harnesseng/runner/aether2/jobs.py)

## 2. Fresh G1 evidence

Final focused rerun after the G2-runner/container/verifier changes:

```bash
python3 -m pytest tests/test_aether2_*.py -q -p no:cacheprovider
python3 -m py_compile runner/aether2/*.py tools/run_aether2_g2.py
python3 tools/aether2_genericity_check.py
```

Results:
- `106 passed in 23.99s`
- `py_compile`: exit 0
- `aether2_genericity_check.py`: exit 0

Targeted regression coverage added for the G2 repair path also passes:

```bash
python3 -m pytest tests/test_aether2_bridge_harbor.py tests/test_run_aether2_g2.py tests/test_aether2_sessions.py -q -p no:cacheprovider
```

Result:
- `24 passed in 11.07s`

The G1 count is now 106 because the new work added legitimate coverage.

## 3. G2 repair implemented

Files changed for this repair slice:
- [tools/run_aether2_g2.py](/Users/mohamud/Downloads/harnesseng/tools/run_aether2_g2.py)
- [bridge_harbor.py](/Users/mohamud/Downloads/harnesseng/runner/aether2/bridge_harbor.py)
- [verifier.sh](/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/g2_03_interactive_session/verifier.sh)
- [task.toml](/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/g2_03_interactive_session/task.toml)
- [Dockerfile](/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/g2_03_interactive_session/Dockerfile)
- [test_run_aether2_g2.py](/Users/mohamud/Downloads/harnesseng/tests/test_run_aether2_g2.py)
- [test_aether2_bridge_harbor.py](/Users/mohamud/Downloads/harnesseng/tests/test_aether2_bridge_harbor.py)

Repair details:
- `g2_03` no longer accepts a plain file-output workaround.
- The verifier now requires:
  - `result.txt == 42`
  - harness-authored verifier context file present
  - successful `session_start`
  - successful `session_send`
  - successful `session_read`
  - `42` observed through `session_read`
  - `session_survival == true`
- `tools/run_aether2_g2.py` now:
  - uses Harbor runtime selection instead of forcing host-local execution
  - writes verifier context under `runs/<timestamp>/verifier_context/`
  - cleans up attributable docker containers after grading
  - marks container-runtime startup failures as `invalid_environment`
- `runner/aether2/bridge_harbor.py` now builds a task-local image from `Dockerfile` when a homolog declares `docker_image` but the image is not yet available locally.

## 4. Latest G2 truth

### Superseded false-positive run

The earlier run below is **not** authoritative anymore for G2 readiness:
- [20260612T172021Z](/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260612T172021Z)

Why superseded:
- `g2_03_interactive_session` passed only because its external verifier checked `result.txt` and ignored the missing real interactive session.
- That row had repeated unsatisfied verification evidence around the actual session requirement.

### Current authoritative run

Latest immutable run:
- [20260612T175936Z](/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260612T175936Z)
- [scoreboard.md](/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260612T175936Z/scoreboard.md)
- [result_rows.jsonl](/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260612T175936Z/result_rows.jsonl)
- [pre_run_cleanup.log](/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260612T175936Z/pre_run_cleanup.log)

Command:

```bash
python3 tools/run_aether2_g2.py
```

Board result:
- `g2_01_file_artifact`: `pass`
- `g2_02_service_survives_exit`: `fail`
- `g2_03_interactive_session`: `invalid_environment`
- `g2_04_package_install`: `invalid_environment`
- `g2_05_long_running_job`: `pass`

Why this is blocked:
- `g2_03_interactive_session`
  - truthfully failed to start its required container runtime
  - row status:
    `runtime_unavailable: RuntimeError: failed to build task container: ERROR: Cannot connect to the Docker daemon ... Is the docker daemon running?`
- `g2_02_service_survives_exit`
  - verifier hit host fork pressure during post-exit service check
  - stderr included:
    `/etc/profile: fork: Resource temporarily unavailable`
- `g2_04_package_install`
  - verifier invocation exhausted spawn retries and ended as:
    `BlockingIOError: [Errno 35] Resource temporarily unavailable`

This means the board is not just "not green"; it is presently **invalid for G3 admission**.

## 5. Process pressure and environment evidence

Host checks taken during this repair:

```bash
uptime
docker version
open -a Docker
docker version
```

Observed:
- `uptime` at 18:56 (Europe/London): load averages `25.34 23.11 20.08`
- `docker version` client is installed, but daemon remains unreachable at:
  `unix:///Users/mohamud/.docker/run/docker.sock`
- `open -a Docker` succeeded as a launch request, but a later `docker version`
  still reported no daemon socket

Interpretation:
- The host is still experiencing the same substantive process/fork exhaustion the reviewer called out.
- The tmux-capable container rerun required for honest G2 cannot be executed until Docker daemon is actually running.

## 6. Listener ownership and cleanup

Prior attributable 8123 listeners from earlier G2 work were already identified and cleaned before this phase.

Post-latest-run check:

```bash
lsof -nP -iTCP:8123 -sTCP:LISTEN
```

Result:
- no listeners

Current cleanup state:
- no attributable port-8123 listener remains
- no attributable docker container from this repair remains
- no temp review credential home was created for this phase beyond prior cleaned `/private/tmp` work

## 7. Codex review status

The original parent goal required a real Codex Review closeout.

However, after the substantive `g2_03` false-positive finding, the current user direction was:
- ignore the broken nested Codex Review gate for now
- do not ignore the substantive G2 finding

Accordingly, this phase did not attempt to re-establish G3 readiness via review-process work. The blocking issue is substantive G2/environment truth, not review bookkeeping.

## 8. Exit-criteria assessment

Mandatory criterion status for `READY_TO_BEGIN_G3`:
- detached-job race fixed with regression evidence: `yes`
- 3 consecutive full G1 suites green plus compile/genericity green: `yes` for the earlier three-run set, and the post-repair focused rerun is also green
- definitive G2 is 5/5 with verification_rounds >= 1: `no`
- real Codex Review completed and no accepted/actionable findings remain: `not re-run in this phase per explicit user waiver`
- adversarial pass cannot disprove G1/G2 readiness: `no`
- authoritative closeout written and security/process cleanup complete: `yes, for the current blocked state`

## 9. Final recommendation

Do **not** begin G3.

Immediate next action:
1. Restore a working Docker daemon on this host.
2. Recheck host pressure until verifier/runtime spawns are stable.
3. Rerun `python3 tools/run_aether2_g2.py` in a fresh immutable run directory.
4. Require the next board to show:
   - all 5 rows external-pass
   - `g2_03` proving real interactive session evidence under the new verifier
   - no `invalid_environment` rows
   - no verifier failures caused by fork pressure

Until that happens, the honest state is:
- `PARTIAL_COMPLETE_G2_CONTAINER_AND_PROCESS_PRESSURE_BLOCKED`
