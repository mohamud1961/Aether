# Aether-2 Pre-G3 Readiness Handoff

Date: 2026-06-12

## Verdict

READY_FOR_PRE_G3_REVIEW

Aether-2 has passed G1 and G2 after the jobs/service-survival corrections.

## Evidence

### G1

Mac full Aether-2 suite passed after jobs.py fixes:

- `python3 -m pytest tests/test_aether2_*.py -q -p no:cacheprovider`
- Result: `108 passed`

Focused post-patch slice also passed:

- `tests/test_aether2_jobs.py`
- `tests/test_run_aether2_g2.py`
- `tests/test_aether2_bridge_harbor.py`
- `tests/test_aether2_sessions.py`
- Result on VM: `32 passed in 2.94s`

Static checks passed on VM:

- `python3 -m py_compile runner/aether2/*.py tools/run_aether2_g2.py`
- `python3 tools/aether2_genericity_check.py`

### G2

Clean Linux VM:

- Host: `harnesseng-dev`
- Path: `/home/azureuser/harnesseng_aether2`
- Docker: available
- Load before run: low
- Run timestamp: `20260612T185102Z`

Scoreboard:

| homolog | status |
|---|---|
| g2_01_file_artifact | pass |
| g2_02_service_survives_exit | pass |
| g2_03_interactive_session | pass |
| g2_04_package_install | pass |
| g2_05_long_running_job | pass |

Artifact paths:

- `tracking/collab/aether2_g2_homologs/runs/20260612T185102Z/scoreboard.md`
- `tracking/collab/aether2_g2_homologs/runs/20260612T185102Z/result_rows.jsonl`

## Fixes included

### JobRegistry fixes

- Detached jobs now default to the task workspace root, not `.aether2`.
- Docker-backed job wrapper paths are translated into the container namespace.
- Job wrapper no longer uses nested `bash -lc`; it uses the existing wrapper shell with `eval`.

### G2 service-survival homolog fix

- `g2_02_service_survives_exit` now provides `workspace_fixture/server_ok.py`.
- Instruction explicitly requires starting `server_ok.py` using `start_job`.
- This prevents the model from accidentally starting `python3 -m http.server`, which returns directory listings instead of `ok`.

## Important caveats

- Mac was not a reliable G2 host due repeated fork/resource pressure.
- VM is the trusted G2 validation host.
- Full VM suite had earlier mirror/path-only failures because the VM used a minimal tar tree, but the G2-relevant validation slice and direct static checks passed.
- The surviving port 8123 listener after G2 is expected for the service-survival task and should be killed after evidence capture.

## Next gate

Proceed to pre-G3 review only.

Do not start official Harbor/G3 until the G3 entry checklist is prepared and reviewed.
