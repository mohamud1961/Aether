# Task: Restore multi-service readiness and cleanup

You are given a broken service orchestration setup with misleading port docs.

Goal:
- start the correct service chain,
- validate real readiness with repeated probes,
- avoid wrong-port false success,
- clean up spawned processes, and
- output `candidate/readiness_receipt.json`.

Discovery requirements:
- do not assume default ports from stale docs;
- identify the live health route from runnable artifacts in the workspace before setting `service_url`;
- include the exact probe command sequence in `notes`.

Required receipt fields:
- `service_url`
- `probes_passed`
- `wrong_port_rejected`
- `cleanup_performed`
- `notes`
