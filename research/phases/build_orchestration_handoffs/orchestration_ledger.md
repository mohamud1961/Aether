# Aether-2 Orchestration Ledger

Last updated: 2026-06-11

## Objective

Build Aether-2 as a new harness line through G1:
- all `tests/test_aether2_*.py` green
- `tools/aether2_genericity_check.py` green
- no G2 work before G1 is green

## Scope

In scope:
- `runner/aether2/`
- `tests/test_aether2_*.py`
- `tools/aether2_genericity_check.py`
- `scripts/deallocate_harnesseng_vm.sh`
- `scripts/configure_harnesseng_vm_autoshutdown.sh`
- `tracking/collab/aether2_build_spec/predictions.md`
- existing-file edits only for:
  - `AGENTS.md`
  - `runner/README.md`
  - `scripts/build_harnesseng_runtime_bundle.sh`

Out of scope for direct edits unless the spec later names an exception:
- historical MLPCP V3 files
- `runner/kernel_*.py`
- `blocks/` guard files
- `runner/packet07_*`
- `runner/successor_*`
- tracking archives outside the approved Aether-2 collab surfaces

## Binding Edit Policy

- Primary implementation lives in `runner/aether2/`.
- Old MLPCP/kernel/blocks files are harvest-only.
- Reject any worker patch that edits a harvest-only or do-not-touch file without a spec-backed reason.
- Prefer many compact worker tasks over broad lane-sized tasks.
- Worker write scopes must be disjoint.
- All work stays in the main checkout on `main/master`; no worktrees and no branch-based execution.

## Setup Checks

| Check | Status | Evidence |
|---|---|---|
| Build spec read enough to execute Hour-0 | complete | `tracking/collab/aether2_build_spec/AETHER2_BUILD_SPEC.md` sections 4, 5, 12, 14, 15, 16 reviewed |
| Repo structure inspected | complete | `tracking/collab/`, `runner/`, `tests/`, `tools/`, `scripts/` present |
| Harvest sources identified | complete | see `decision_log.md` entry D-003 |
| `codex-review` availability checked | complete | skill present in environment |
| Formal Goal required for orchestrator? | complete | no; direct orchestration per principal correction |
| Worker delegation mechanism checked | complete | Codex thread tools available; thread-based delegation in use |
| Hour-0 contract freeze recorded | complete | `hour0_contracts.md` |
| Predictions file existence checked | complete | `tracking/collab/aether2_build_spec/predictions.md` exists |
| Main checkout confirmed | complete | `git branch --show-current` -> `master` |
| Runtime bundle Aether-2 inclusion checked | complete | `scripts/build_harnesseng_runtime_bundle.sh` already includes `runner/`, `tools/`, and `tests/`; comment added |

## Worker Policy

Every worker packet must include:
- exact files allowed to create/edit
- exact harvest-only files allowed to inspect
- explicit do-not-touch list
- exact acceptance criteria
- exact tests/checks
- interface sketch from the spec
- anti-benchifying constraints
- required handoff format
- explicit instruction not to redesign architecture

Workers must also:
- use Goal structure when available, or explicitly report the fallback
- use `codex-review` when available for closeout, or explicitly report the fallback
- avoid reverting other workers' edits
- run as pinned Codex threads, not subagents
- default to `gpt-5.4-mini`
- `gpt-5.4-mini` may use `high`/`xhigh` reasoning for narrow reasoning-heavy slices
- use `gpt-5.4` only by exception for integration-sensitive or ambiguity-heavy tasks, and only at low/medium reasoning
- implement the full file-level spec contract for their slice, not a knowingly thin placeholder
- receive a contract-complete packet: manifest row, interfaces, behaviors, cross-cutting constraints, acceptance checklist, and tests for the full component contract
- mark the handoff `partial` with exact missing items if a required behavior cannot be completed inside the slice
- use the manual review checklist by default while the shared `codex-review` helper blocker remains unresolved

## Active Tasks

| ID | Owner | Model | Status | Write Scope | Harvest Scope | Tests / Checks | Review | Integration | Goal / Review Availability | Blockers |
|---|---|---|---|---|---|---|---|---|---|---|
| O-001 | orchestrator | gpt-5.5 | complete | `tracking/collab/aether2_build_orchestration/*` | build spec only | none | self | merged | review yes / goal optional | none |
| O-002 | orchestrator | gpt-5.5 | complete | `tracking/collab/aether2_build_orchestration/hour0_contracts.md` | build spec only | none | self | merged | review yes / goal optional | none |
| W-001 | `019eb771-0c19-7113-b158-66db4da71f9c` | gpt-5.4-mini | accepted; genericity-clean; integration-ready candidate | `runner/aether2/prompts.py`, `tests/test_aether2_prompts.py` | spec only | `python3 -m pytest tests/test_aether2_prompts.py` rerun: `3 passed` | accepted on revised self-contained prompt after parent runtime-contract review | merged in main checkout | Goal used in follow-up; `codex-review` attempted but helper failed on env config parse | review-helper environment issue noted; prompt now carries doctrine lines inside `SYSTEM_PROMPT` |
| W-002 | `019eb771-1cd6-7301-ae9b-a66e4e0f013b` | gpt-5.4-mini | superseded by W-014 | `runner/aether2/envelope.py`, `tests/test_aether2_envelope.py` | spec only | superseded local rerun: `python3 -m pytest tests/test_aether2_envelope.py` -> `4 passed` after W-014 | parent audit correctly flagged the original packet as spec-incomplete; follow-up closed the missing process/error contract | merged in main checkout | worker reported tooling only | track this as orchestration prompt debt corrected by W-014 |
| W-003 | `019eb771-29bf-78c3-b16d-84bd0a94e645` | gpt-5.4-mini | superseded by W-017 | `runner/aether2/tools.py`, `tests/test_aether2_tools.py` | spec only | superseded local rerun: `python3 -m pytest tests/test_aether2_tools.py` -> `13 passed` after W-017 | parent audit correctly required fuller provider-native schema contracts; follow-up closed the gap | merged in main checkout | worker reported tooling only | track this as orchestration prompt debt corrected by W-017 |
| W-004 | `019eb771-33d7-7fc0-9ced-011c1d962128` | gpt-5.4-mini | accepted for mechanical CI gate; promotion gates remain external | `tools/aether2_genericity_check.py`, `tests/test_aether2_genericity.py` | spec only | `python3 -m pytest tests/test_aether2_genericity.py` rerun: `2 passed` | local review accepted follow-up for spec item 4 | merged in main checkout | Goal used in follow-up; `codex-review` attempted but helper failed on env config parse | broader spec items 5-6 remain orchestration-level follow-up work |
| W-005 | `019eb771-3fb2-7293-83ba-9f59facdedb5` | gpt-5.4-mini | functionally green; superseded by W-016 | `runner/aether2/metrics.py`, `tests/test_aether2_metrics.py` | `runner/action_bus.py` | original rerun: `python3 -m pytest tests/test_aether2_metrics.py` -> `2 passed` | initial slice closed by follow-up because parent audit flagged missing §4.11 post-hoc action-type labeling | merged in main checkout | worker reported tooling only | superseded by W-016 for full file-level contract on action-type labeling |
| W-006 | `019eb771-1cd6-7301-ae9b-a66e4e0f013b` | gpt-5.4-mini | blocked; re-dispatched as W-009 | `runner/aether2/receipts.py`, `tests/test_aether2_receipts.py` | spec + approved host_receipts layout refs | none | worker thread hit budget limit before implementation | none | Goal requested | no code written; thread budget-limited |
| W-007 | `019eb771-29bf-78c3-b16d-84bd0a94e645` | gpt-5.4-mini | functionally green; superseded by W-013 | `runner/aether2/orientation.py`, `tests/test_aether2_orientation.py` | spec + approved mlpcp orientation harvest ref | original rerun locally: `python3 -m pytest tests/test_aether2_orientation.py` -> `3 passed` | initial slice closed by follow-up because the original packet did not carry the full §7 component contract | merged in main checkout | Goal + review attempted | superseded by W-013 for full orientation contract breadth |
| W-008 | `019eb771-3fb2-7293-83ba-9f59facdedb5` | gpt-5.4-mini | partial; spec-incomplete | `runner/aether2/delta.py`, `tests/test_aether2_delta.py` | spec + `runner/kernel_artifacts.py` + `runner/kernel_state.py` | `python3 -m pytest tests/test_aether2_delta.py` rerun: `2 passed` | local review complete, but parent audit flagged registry slots as honest placeholders rather than the full §10 cross-cutting contract | merged in main checkout | Goal + review attempted | process/job/session/service state capture is still minimal and may be insufficient for envelope/mirror/verify integration |
| W-009 | `019eb771-0c19-7113-b158-66db4da71f9c` | gpt-5.4-mini | functionally green; superseded by W-015 | `runner/aether2/receipts.py`, `tests/test_aether2_receipts.py` | spec + approved host_receipts layout refs | original rerun locally: `python3 -m pytest tests/test_aether2_receipts.py` -> `2 passed` | initial slice closed by follow-up because the original packet did not carry the full serializer-robustness contract | merged in main checkout | Goal + review requested explicitly | superseded by W-015 for robust normalization of non-JSON-serializable payloads |
| W-010 | `019eb771-29bf-78c3-b16d-84bd0a94e645` | gpt-5.4-mini | accepted tiny follow-up; parent slice W-007 remains partial | `runner/aether2/orientation.py`, `tests/test_aether2_orientation.py` | none beyond current file context | worker reported `python3 -m pytest tests/test_aether2_orientation.py` -> `3 passed` | docstring follow-up accepted | merged in main checkout | Goal + review requested explicitly | only addressed genericity compliance, not the broader §7 surface gap |
| W-011 | `019eb771-3fb2-7293-83ba-9f59facdedb5` | gpt-5.4-mini | accepted tiny follow-up; parent slice W-002 remains partial | `runner/aether2/envelope.py`, `tests/test_aether2_envelope.py` | none beyond current file context | worker reported `python3 -m pytest tests/test_aether2_envelope.py` -> `3 passed` | docstring follow-up accepted | merged in main checkout | Goal + review requested explicitly | only addressed genericity compliance, not the broader process/error contract gap |
| W-012 | `019eb771-1cd6-7301-ae9b-a66e4e0f013b` | gpt-5.4-mini | accepted tiny follow-up; parent slice W-003 remains functionally green | `runner/aether2/tools.py`, `tests/test_aether2_tools.py` | none beyond current file context | worker reported `python3 -m pytest tests/test_aether2_tools.py` -> `13 passed` | docstring follow-up accepted | merged in main checkout | Goal + review requested explicitly | only addressed genericity compliance, not the broader tool-contract depth review |
| W-013 | `019eb771-29bf-78c3-b16d-84bd0a94e645` | gpt-5.4-mini | accepted; functionally green; integration-ready candidate | `runner/aether2/orientation.py`, `tests/test_aether2_orientation.py` | spec + approved MLPCP env-map harvest ref | worker reported `python3 -m pytest tests/test_aether2_orientation.py` -> `3 passed`; local combined rerun confirmed `3 passed` | fuller §7 packet accepted after prompt-debt correction; manual self-review accepted after known `codex-review` config failure | merged in main checkout | Goal + review required explicitly | `network` remains a compact string alongside `network_reachable` and `network_evidence`; a later structured-network object would be additive rather than required now |
| W-014 | `019eb771-33d7-7fc0-9ced-011c1d962128` | gpt-5.4-mini | accepted; functionally green; integration-ready candidate | `runner/aether2/envelope.py`, `tests/test_aether2_envelope.py` | spec + `runner/kernel_recovery.py` + `blocks/execution/flat_loop.py` | worker reported `python3 -m pytest tests/test_aether2_envelope.py` -> `4 passed`; local rerun confirmed `4 passed` | envelope contract deepening accepted after explicit process/job/session/service delta fields and truthful error reason-code coverage review | merged in main checkout | Goal + review required explicitly | current fields satisfy Hour-0 envelope semantics; wider loop integration will still validate exact producer/consumer shapes |
| W-015 | `019eb771-0c19-7113-b158-66db4da71f9c` | gpt-5.4-mini | accepted; functionally green; integration-ready candidate | `runner/aether2/receipts.py`, `tests/test_aether2_receipts.py` | spec + approved host_receipts layout refs | worker reported `python3 -m pytest tests/test_aether2_receipts.py` -> `3 passed`; local combined rerun confirmed `3 passed` | serializer robustness gap closed; manual self-review accepted after known `codex-review` config failure | merged in main checkout | Goal + review required explicitly | serializer is intentionally conservative; more exotic cyclic object shapes may need later coverage, but the required bounded contract is now present |
| W-016 | `019eb771-3fb2-7293-83ba-9f59facdedb5` | gpt-5.4-mini | accepted; functionally green; integration-ready candidate | `runner/aether2/metrics.py`, `tests/test_aether2_metrics.py` | spec + `runner/action_bus.py` | worker reported `python3 -m pytest tests/test_aether2_metrics.py` -> `3 passed`; local rerun confirmed `3 passed` | §4.11 labeling gap closed; manual self-review accepted after known `codex-review` config failure | merged in main checkout | Goal + review required explicitly | `tool_invocations` source-shape extraction is heuristic across several likely keys; `pass_` compatibility surface still worth watching during wider integration |
| W-017 | `019eb771-1cd6-7301-ae9b-a66e4e0f013b` | gpt-5.4-mini | accepted; functionally green; integration-ready candidate | `runner/aether2/tools.py`, `tests/test_aether2_tools.py` | spec only | worker reported `python3 -m pytest tests/test_aether2_tools.py` -> `13 passed`; local rerun confirmed `13 passed` | provider-native tool contract deepening accepted with exact 10-tool surface preserved | merged in main checkout | Goal + review required explicitly | schema usability will still be exercised during loop integration, but the file-level contract is now strong enough to proceed |
| W-018 | `019eb771-3fb2-7293-83ba-9f59facdedb5` | gpt-5.4-mini | accepted; functionally green; integration-ready candidate | `runner/aether2/executor.py`, `tests/test_aether2_executor.py` | spec + `runner/aether2/envelope.py` + hour-0 contracts | worker produced code but exhausted its own token budget before validation; orchestrator completed local verification with `python3 -m pytest tests/test_aether2_executor.py` -> `3 passed` | accepted after orchestrator repaired one boundary-guard bug and stabilized the test strategy for this environment's process-cap limits | merged in main checkout | Goal used in worker thread; `codex-review` still env-blocked | executor is honest about workspace-root boundaries and spawn failures, but this local fallback is not a real container backend yet |
| W-019 | `019eb771-0c19-7113-b158-66db4da71f9c` | gpt-5.4-mini | accepted; functionally green; integration-ready candidate | `runner/aether2/mirror.py`, `tests/test_aether2_mirror.py` | spec + `runner/aether2/delta.py` | worker reported `python3 -m pytest tests/test_aether2_mirror.py` -> `5 passed`; local combined rerun confirmed `5 passed` | contract-complete mirror slice accepted | merged in main checkout | formal Goal used in worker thread; `codex-review` attempted but helper failed on env config | loop/tail integration still needed to surface mirror notes at runtime |

## Integration Notes

- Accepted in main checkout after local rerun or reviewed worker follow-up: W-001, W-004, W-010, W-011, W-012.
- W-002, W-007, W-008, and W-009 are now tracked as partial/spec-incomplete rather than accepted, per the tightened full-spec acceptance rule.
- New follow-up worker wave dispatched: W-013 orientation contract, W-014 envelope contract, W-015 receipts robustness, W-016 metrics labeling, W-017 tool-contract depth.
- W-013, W-014, W-015, W-016, and W-017 have completed and close the previously recorded orientation breadth, envelope contract, receipts robustness, metrics labeling, and tool-contract depth gaps.
- W-018 executor contract and W-019 mirror contract have also completed and are locally accepted after orchestrator verification.
- VM lifecycle scripts were missing in the live checkout despite earlier status assumptions; both `scripts/deallocate_harnesseng_vm.sh` and `scripts/configure_harnesseng_vm_autoshutdown.sh` are now present, executable, and smoke-checked with `--dry-run --help`.
- Model-client contract review now has explicit route-level TPM pacing proof, 429/5xx retry coverage, and non-transient fail-fast coverage in `tests/test_aether2_model_client.py`; the wrapper remains thin and honest.
- Harbor bridge adversarial review completed with workspace-to-artifacts sync-back hardening, visible-artifact enforcement, and stronger bridge tests; local rerun confirms `python3 -m pytest tests/test_aether2_bridge_harbor.py tests/test_aether2_model_client.py` -> `9 passed`.
- Whole-spec audit re-confirmed that the only file-level build blockers are `runner/aether2/jobs.py`, `runner/aether2/sessions.py`, and `runner/aether2/loop.py`; current support-module board is green for the files that exist.
- Current Aether-2 grouped board for existing surfaces is green: `python3 -m pytest tests/test_aether2_*.py` -> `63 passed`; `python3 tools/aether2_genericity_check.py` -> exit 0.
- Remaining run-critical open work is still `jobs.py`, `sessions.py`, `loop.py`, final synthetic loop/bridge end-to-end verification, written small-run plan, and final review-gate closeout.
- Fresh same-directory worker wave now in flight:
  - W-020 jobs contract
  - W-021 sessions contract
  - W-022 delta contract deepening
  - W-023 adversarial context/compactor review
  - W-024 adversarial verify review
  - W-025 adversarial model-client review
  - W-026 adversarial Harbor bridge review
  - W-027 read-only whole-spec gap audit
  - W-028 review-gate diagnosis
- Earlier W-020/W-021 and the first "fresh" W-029/W-030 replacements stalled without implementation and were archived after thread-level failures.
- Active runtime-registry replacements are now:
  - W-031 jobs registry final contract — thread `019eb7c4-5397-7ed3-8bce-21b5755e2327`
  - W-032 sessions registry final contract — thread `019eb7c4-5ac5-7c52-ba62-d5d218a42a3b`
- A worker-packet transport bug briefly double-wrapped W-031/W-032 in escaped delegation text; orchestrator corrected both threads with direct plain follow-up instructions rather than redispatching again.
- Root-cause correction adopted: when a slice is spec-incomplete because the worker packet omitted part of the component contract, track that as orchestration prompt debt rather than framing it as a worker-quality failure.
- Re-audit from this angle:
  - W-002 envelope, W-005 metrics, W-007 orientation, W-008 delta, and W-009 receipts were all originally dispatched from narrower packets than the full component rows required.
  - W-003 tools belongs in that same prompt-debt bucket; its full contract was only completed by W-017.
  - The corrective action is the contract-complete follow-up wave W-013 through W-017, not blame on the original workers.
- Earlier `multi_agent_v1` subagents were closed after the principal switched policy to Codex-thread-only workers.
- `codex-review` helper showed a shared environment/config blocker on worker follow-up attempts: `unknown variant 'default', expected 'fast' or 'flex' in service_tier`; a dedicated diagnosis lane is now responsible for restoring or replacing that gate.
- One combined local board run failed due transient process-capacity limits while a genericity test spawned a subprocess; this was an environment/runtime failure, not a code assertion failure.

## Escape Hatches

If a worker mechanism fails:
- record the exact tool failure
- keep the write scope reserved
- re-dispatch using the next available agent/thread mechanism
- do not silently collapse into single-agent execution unless all delegation paths are unavailable and documented
