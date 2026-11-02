# Bounded local Linux qualification for the state service

Objective: exercise the existing Core-owned state service and transparent
known-good/known-bad fixture inside an isolated Linux container. This is a
provider-free runtime diagnostic, not a Luna accuracy board or promotion.

- Source: Git commit `2b4cdad7ba5f077dba7f456ad14ab0e9354b1ee1`. The exported
  Core source, Core tests and synthetic fixture archive has SHA-256
  `f8a86d2b48c51a85e599ccd8d12b90801dee3737ed02a368c0a71e866c8b357d`.
- Python dependencies: exported from the locked Core environment; requirements
  SHA-256 `1fec19e0250fcc5e54cdde0700cc29a34004e1eb267d36b29d9e294177bad427`.
- Runtime: a new local Colima profile, `codex-core-state-qual-20261102`, at
  most one CPU, 1 GiB memory, 4 GiB data disk and 5 GiB root disk. It must
  not activate or alter the user's Docker context, SSH configuration, or
  existing stopped profile. No host directories or SSH agent are mounted.
- Image: Linux ARM64 `python:3.12-slim` manifest
  `sha256:b224e2fe306f9d303251ada22961635e5b52a69c0414a0050611be31c59f5f5b`,
  obtained from the public Docker Hub tag metadata on 2 November 2026.
- Scope: the four facts-focused Core test files plus the two REPL retention
  controls and `qa/evals/provided_state` with its frozen five synthetic cases.
  The fixture's own final-artifact grader and unavailable-observer control
  are included. No hidden task tests, solutions, verifier logs, keys,
  held-out tasks, real task workspaces, model calls or Gateway are used.
- Network: anonymous public image and dependency setup only; the test
  container runs with networking disabled and no host mounts. Its process
  namespace and private temporary paths are independent of the host.
- Cost: **£0 paid/cloud/model spend**. This is a bounded local VM, not an
  Azure VM. Setup is attempted once and is capped at five minutes; test
  execution is capped at five minutes. A failed setup or test is preserved as
  invalid/failing evidence, not retried with a different source or image.
- Cleanup: stop and remove only the profile and containers created for this
  gate after saving evidence; check that they are no longer active. Do not
  start, stop, change, or delete the user's existing Colima profile.
- The local supervisor is `qa/local_state_linux_gate.py`, SHA-256
  `cd270f3bc0c490251b459e5156d08d55a346073421a1646e822eef93c3ca655e`.
  Before launch, its process-ownership controls passed with fake executables:
  it refused a pre-existing profile, and a failed new-profile startup cleaned
  only the newly named profile (2 passed). Those fakes do not qualify Linux.

Exit evidence must identify the actual source archive, image digest, runtime,
test command, outcomes, fixture controls, and owned process/VM cleanup. A
pass cannot establish Luna's behavior, token cost, or task success. Failed or
incomplete setup does not qualify the service for default promotion.

## Targeted retry after an invalid launch

The first attempt reached the Linux container, but its test command exited
before running tests: the image retained the builder's `sh` entrypoint and
the supervisor supplied a second `sh` as a script name. The original host
summary and launch log are preserved under `qa/evidence/state_linux_2b4cdad7/`.
The owned profile was removed, the user's other profile stayed stopped and
the active Docker context remained `default`.

The sole runner correction explicitly selects `sh` as the test container's
entrypoint and passes `-c` once. A third fake-process control checks that
entrypoint and the network-disabled container setting; all three supervisor
controls pass. One retry uses the exact same source archive, requirements,
image digest, task pack, budget and resource/cleanup limits, with separate
evidence at `qa/evidence/state_linux_2b4cdad7_retry1/`. The corrected
supervisor SHA-256 is
`94f9f5bd8b8ddb6b04832775be0af28014437aea1797b9b7b88b5b3abd4642bd`.

## Result

The corrected retry ran Linux `6.8.0-117-generic aarch64` in the declared
container with `network=none` and zero mounts. The facts and REPL checks
passed (48 passed); the synthetic pack's five artifact controls and five
sensor controls passed. The deliberately unavailable observer retained the
correct artifact controls but failed four of five sensor controls and exited
nonzero, as required. Source and fixture hashes were independently compared
with commit `2b4cdad7` with no mismatches. The owned profile was stopped and
deleted; the user's existing profile stayed stopped and Docker's active
context stayed `default`.

Evidence is under `qa/evidence/state_linux_2b4cdad7_retry1/`. This qualifies
only the stated local Linux/container controls for this source. It is not a
full benchmark-native task-success, latency, provider-cost, or promotion
result; the archived real machines were not reconstructed.

## Requalification after the long-run receipt fix

The receipt-window fix changed Core after the Linux run above. A fresh local
Linux check is sealed for source `77c0ddeb71ec1e58a4020906b8ae6da7a2ec9b95`
(state runtime `c5074015`) with the same image, locked requirements, profile,
isolation, cleanup, no-model and £0 limits. The new source archive SHA-256 is
`787ef2507eb9fc2f9345e5a876a07edc94d35dbd69b0f231abbd08442578ce3b`.

It repeats the 48 state/REPL controls and the five-case good and unavailable
observer controls. It also measures the existing three-block scripted Core
overhead screen inside the isolated Linux container; the overhead numbers are
reported separately and are not automatically interpreted as task success.
The derived supervisor is `qa/evidence/state_linux_77c0ddeb_supervisor.py`,
SHA-256 `142f7c5f9e5fb1deed1ff66bd20e517cc413bb71fed89d8ff0cbb50a6dc5bd4b`.
Its diff from the already tested supervisor is limited to the owned paths,
source archive hash, local image/container names, and overhead measurement.
Results go to the separate `qa/evidence/state_linux_77c0ddeb/` directory.

The recheck passed: 48 state/REPL tests, all five artifact controls and all
five state sensor controls. The unavailable-observer control correctly
failed four sensors and exited nonzero. Source, pack and runner hashes were
independently matched to `77c0ddeb`; the container had no network or host
mounts. The owned profile was removed; the pre-existing profile stayed
stopped and Docker's active context stayed `default`.

On the separate three-block synthetic overhead screen, median state-on
request text was 1.354 times state-off, with 50 versus 43 environment
executions. Median local wall time was 1.326 seconds on versus 1.190 seconds
off. This is a small synthetic measurement, not provider tokens, billed
cost, live Luna performance or a task-success estimate. It remains an
efficiency concern, not evidence to promote the service by itself.
