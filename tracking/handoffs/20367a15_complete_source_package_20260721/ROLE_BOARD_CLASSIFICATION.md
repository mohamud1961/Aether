# Solver and Verifier role-board classification

## Authority and execution

- Production commit: `20367a15b919cc82dae0adcc17ef1826874f3773`
- Production tree: `f32652cf58195ba74a3061f7f5b10a126d67ae28`
- Exact package manifest: `1ac7efe9241cc635d6fcffb1a3653ae10ea5b373090ae470a0ffea50155d596e`
- Solver Gateway run: `d593452472b0b49a`
- Verifier Gateway run: `ae2ea6a3be904a99`
- Solver evidence bundle: `a52b38366a458e7df8800f8a8875cc3941d219c23ad5f1515c67daa6e9064901`
- Verifier evidence bundle: `90a517e1db7657c8286a95a2491acf12136018bf1534d89d305919c5a62b9e38`

The boards ran concurrently on the upgraded Azure VM in independent source
workspaces and sibling output directories. Both source workspaces ended clean
at the exact commit and tree above. The Gateway completion events were
processed under their original run IDs; no duplicate run was launched.
After evidence retrieval, the VM was restored from `Standard_D32ds_v4` to its
original `Standard_D16ds_v4` size and Azure reported `VM deallocated`. No
containers or temporary Gateway listener remained active.

## Solver result

Status: **finalized, invalid as a model-quality board, non-promotable**.

- Rows: 24/24
- Provider/parse valid: 4/24 (16.7%)
- Protocol valid: 4/24 (16.7%)
- Expected decisive actions among all rows: 4/24 (16.7%)
- Expected decisive actions among scorable rows: 4/4 (100%)
- Azure request rejection before generation: 18/24
- Multiple distinct assistant outputs, failed closed: 2/24
- Strict promotion: false
- Final marker: `579d4e1865b5c7918870a0f1ddf0e6aa1b4ba14a86b979f12c0d61db8e431be5`
- Aggregate: `3f3b5b74eb365e840c94eba9e9fda6ad8dd97628294e94b7dd63361ef2e6134a`

The dominant failure is owned by the provider/request contract, not Solver
semantics. The production Azure callable always requests
`text.format.type=json_object`, but 18 checkpoint message sets did not contain
the word `json`; Azure rejected those requests with HTTP 400 before a model
output existed. The four cases that happened to include `json` in their
model-visible content were accepted. This content-dependent split is direct
evidence of a generic request-construction defect.

The two remaining invalid rows each contained multiple distinct assistant
outputs. Canonicalization correctly refused to select one, retained candidate
hashes and item IDs, and emitted a normal invalid row. Those are provider-output
invalids, not model-quality scores.

The four valid rows all chose the expected `read_file` action. Missing
commitment fields are advisory in this production schema and were not used to
invalidate otherwise correct actions. No requirement was relaxed for this
classification.

### 24-row Solver diagnostic

`raw_sha256` identifies the selected raw output. The SHA-256 of empty bytes on
invalid rows means no canonical raw output was selected; candidate hashes for
the two ambiguity rows remain in `summary.json` telemetry.

| Case | Sample | Classification | Raw SHA-256 | Semantic action | Missing advisory fields |
|---|---:|---|---|---|---|
| inspect_before_edit | 1 | valid/pass | `7db609bc12f87475fc28ee5982b0d3c60135f431da2256a5e80dfa30df7b11ee` | expected `read_file` | evidence_gap, expected_observation, if_fail_next, intent |
| inspect_before_edit | 2 | provider multiple outputs | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not scored | n/a |
| inspect_before_edit | 3 | valid/pass | `d8e5c3784c0e274d94b3d26b9b83df9f5e5523db9e2a64e73435d6e4f62d6092` | expected `read_file` | evidence_gap, expected_observation, if_fail_next, intent |
| failed_command_pivot | 1 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| failed_command_pivot | 2 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| failed_command_pivot | 3 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| service_launch_then_fresh_probe | 1 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| service_launch_then_fresh_probe | 2 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| service_launch_then_fresh_probe | 3 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| large_output_handle_retrieval | 1 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| large_output_handle_retrieval | 2 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| large_output_handle_retrieval | 3 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| stale_evidence_after_mutation | 1 | valid/pass | `7fcc4f4486bfa1fe07ace1a9777c882c778fb326fc9fe0796681d06ecaaa0b85` | expected `read_file` | expected_observation, if_fail_next, intent |
| stale_evidence_after_mutation | 2 | valid/pass | `e0bd94c6c25521e1b87af0e74ec4be35fe826f658c82979938005060c76938b8` | expected `read_file` | expected_observation, if_fail_next, intent |
| stale_evidence_after_mutation | 3 | provider multiple outputs | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not scored | n/a |
| verifier_finding_repair | 1 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| verifier_finding_repair | 2 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| verifier_finding_repair | 3 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| derived_representation_lineage | 1 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| derived_representation_lineage | 2 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| derived_representation_lineage | 3 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| submission_coherence | 1 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| submission_coherence | 2 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |
| submission_coherence | 3 | Azure JSON-mode 400 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | not generated | n/a |

## Verifier result

Status: **finalized, complete as evidence, non-promotable**.

- Rows: 5/5
- Known-bad detections: 3/3
- Known-good acceptances: 0/2
- Valid semantic rows: 4/5
- Provider-invalid rows: 1/5
- Final marker: `5f0ac16eeca08758bcb1b5d6073e97a3d924daca2a32e94d333a4e705ac8627f`
- Aggregate: `a0eab66bd0a5864686491e40f325405c55a95078d7863f7256745224d10b8fd4`

| Task | Expected | Result | Measurement | Classification |
|---|---|---|---|---|
| kv-store-grpc | known bad | `needs_repair` | valid | HIT |
| gcode-to-text | known bad | `uncertain_missing_evidence` | valid | HIT |
| video-processing | known bad | `uncertain_missing_evidence` | valid | HIT |
| log-summary-date-ranges | known good | `needs_repair` | valid | MISS; false positive against an official-grader-passed frozen state |
| code-from-image | known good | no verdict | provider invalid | INVALID_PROVIDER after bounded inspection sequence |

The evaluator did fail closed correctly: the invalid provider response became a
normal result row, raw provider telemetry was retained, later evidence was
finalized, and the marker records the board as invalid. The prior crash class is
therefore repaired. The Verifier model route still fails its promotion gate due
to one false positive and one invalid known-good row.

## Production-path audit

Both runners instantiate the production `ModelHooks`, production Azure
callable, strict parser, compiled action schema, provider canonicalization, and
production verifier inspection loop. The Solver runner builds messages with
the production `build_solver_messages` path. The Verifier runner builds the
production verifier packet and invokes `verify_with_inspector`.

The boards intentionally supply frozen/synthetic role-eval context rather than
launching a full official TerminalBench task. That difference is the role-board
boundary, not a bypass of the model/provider/parser path. These rows are role
qualification evidence and are not official benchmark rewards.

## Decision

- Deterministic certification remains green and unchanged.
- Solver promotion is blocked by a generic provider/request integration defect;
  the observed 4/4 scorable semantic result is insufficient for promotion.
- Verifier promotion is blocked by known-good specificity and provider-output
  reliability.
- No Architect, perception, smoke, or official board is authorized from these
  results.
- The next goal should first add a falsifiable provider-request contract test,
  make every JSON-mode request contain an explicit JSON instruction, rerun the
  same Solver board, then diagnose the two Verifier known-good failures without
  weakening evidence requirements.

## Gateway runtime note

The Gateway initially reported launch errors even though the VM jobs started.
Its environment-value log redactor treated the short safe value `1` as a secret
and replaced digits inside remote-control JSON, corrupting PID parsing. The
jobs were recovered by their durable receipts and were not relaunched. A
temporary scoped Gateway runtime repair (redact only values of at least eight
characters) passed six focused tests and allowed the watcher to process each
completion once. Native thread resumption failed, but the active heartbeat and
durable run receipts preserved control. This temporary Gateway repair is not a
change to certified Aether source and should be applied/reviewed separately.
