# Task card: service_lifecycle_readiness (v2)

Admission: **debug**. The grader executes the candidate on the host, and isolated grading is not yet qualified.
Reference, known-bad and careless controls test this v2 design.

## Design (v2)

- Goal-level ticket: a red readiness probe after a clean-up.
- The contract (1.1) has a changelog and a superseded 0.9 section. The notes, an old attempt and a probe log
  disagree with it (port 18920, `text/plain` health, optional shutdown).
- The scaffold's signal handler calls `server.shutdown()` on the serving thread, which deadlocks.
- The grader probes status codes, media types and bodies, an unknown path, a 2 second window and clean SIGTERM exit,
  and hashes every pristine file. The visible checker keeps its shape-level probe.

## Controls

- Known-bad: 8 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| missing_service_impl | careless do_nothing, wrong_target |
| service_did_not_bind | known_bad wrong_port; careless fake_it |
| health_response_mismatch | known_bad health_wrong_version |
| health_content_type_mismatch | known_bad health_text_plain |
| health_status_mismatch | careless skip_check |
| echo_response_mismatch | known_bad echo_wrong_key |
| echo_status_mismatch | careless half_done |
| service_crashed_before_second_observation | known_bad crash_before_second_observation |
| shutdown_timeout | known_bad scaffold_shutdown_deadlock |
| unclean_shutdown | known_bad unclean_shutdown |
| other_file_modified | known_bad tampered_visible_check |
| unknown_path_status_mismatch, port_already_in_use, decoy_file_modified, contract_file_modified | guards only |
