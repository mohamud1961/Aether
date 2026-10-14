# Ceiling: service_lifecycle_readiness (v2)

## What a perfect solution does

1. Reads `spec/service_contract.md` version 1.1 and ignores the superseded 0.9 section (port 18920, key `echoed`).
   It does not follow `ops/oncall_readiness.md` (port 18920, `text/plain` health, optional shutdown) or the old
   attempt under `ops/previous_attempt/`.
2. Writes `out/service_impl.py`, standard library only, bound to `127.0.0.1:18923`:
   - `GET /health` returns 200, `application/json`, body `{"status": "ok", "version": "1.0"}`.
   - `POST /echo` reads the raw UTF-8 body and returns 200, `application/json`, `{"echo": <exact body>}`.
   - Any other GET path returns 404.
   - On SIGTERM it shuts down on another thread (because `HTTPServer.shutdown()` blocks until `serve_forever()`
     returns) and exits 0.
3. Runs the visible check, sees it pass, and knows that passing is not the contract.
4. Leaves every file outside `out/` unchanged.

The reference implements exactly this and hard-codes the method, not the grader's values.

## Grader checks

- Live probes: health status, media type and body (`health_status_mismatch`, `health_content_type_mismatch`,
  `health_response_mismatch`); echo status, media type and body (`echo_status_mismatch`,
  `echo_content_type_mismatch`, `echo_response_mismatch`); unknown GET path (`unknown_path_status_mismatch`).
- Lifecycle: bind within 5 s (`service_did_not_bind`), still answering after a 2 s window
  (`service_crashed_before_second_observation`, `second_health_probe_failed`), clean exit on SIGTERM
  (`shutdown_timeout`, `unclean_shutdown`).
- Port 18923 not already in use before the run (`port_already_in_use`).
- Byte identity of every pristine file (`contract_file_modified`, `decoy_file_modified`, `other_file_modified`).

## Why each known-bad state is wrong

- `health_wrong_version.sh`: `"1.1"` in the body. `health_response_mismatch`.
- `crash_before_second_observation.sh`: exits 1 before the 2 s window ends. `service_crashed_before_second_observation`.
- `wrong_port.sh`: binds to the superseded 18920. `service_did_not_bind`.
- `unclean_shutdown.sh`: exits 3 on SIGTERM. `unclean_shutdown`.
- `echo_wrong_key.sh`: returns `echoed`. `echo_response_mismatch`.
- `health_text_plain.sh`: right body, wrong media type, as the old notes say. `health_content_type_mismatch`.
- `scaffold_shutdown_deadlock.sh`: shutdown on the serving thread never returns. `shutdown_timeout`.
- `tampered_visible_check.sh`: correct service, but the checker is rewritten to pass. `other_file_modified`.

## Careless controls

- `do_nothing.sh`: no service. `missing_service_impl`.
- `fake_it.sh`: prints the answers and exits. `service_did_not_bind`.
- `skip_check.sh`: the scaffold, which returns 404 on health. `health_status_mismatch`.
- `wrong_target.sh`: the right service under `out/service.py`. `missing_service_impl`.
- `half_done.sh`: health only; echo answers 404. `echo_status_mismatch`.

## Grader expectations

- Reference state: `passed: true`, `score: 1.0`.
- Untouched workspace: `passed: false`, with `missing_service_impl`.

Admission stays `debug`: the grader runs the candidate on the host.
