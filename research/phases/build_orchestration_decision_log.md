# Aether-2 Decision Log

## D-001 — Orchestrator works directly, not Goal-gated

- Date: 2026-06-11
- Decision: The orchestrator will work directly from the build spec and thread instructions. Formal Goal usage is optional, not a prerequisite.
- Why: Principal correction explicitly removed Goal setup as a gate and prioritized forward execution.
- Consequence: Governance substance stays in the orchestration artifacts instead of a formal Goal object.

## D-002 — New-files-first implementation policy

- Date: 2026-06-11
- Decision: Aether-2 is implemented primarily in `runner/aether2/` plus the new tests/tools/scripts named in the spec. Existing-file edits are limited to `AGENTS.md`, `runner/README.md`, and `scripts/build_harnesseng_runtime_bundle.sh`.
- Why: Principal correction made the new harness line the primary implementation surface and restricted edits to reduce drift into historical code.
- Consequence: Old MLPCP/kernel/blocks files are harvest-only unless the build spec explicitly says otherwise.

## D-003 — Harvest sources accepted as read-only inputs

- Date: 2026-06-11
- Decision: The orchestrator and workers may inspect, copy patterns from, or adapt logic from the following without editing them:
  - `blocks/execution/flat_loop.py`
  - `blocks/orientation/phase6_doctrine.py`
  - `runner/kernel_compaction.py`
  - `runner/kernel_context_pack.py`
  - `runner/kernel_state.py`
  - `runner/kernel_artifacts.py`
  - `runner/kernel_recovery.py`
  - `runner/kernel_layer2_audit.py`
  - `runner/kernel_tpm_pacer.py`
  - `runner/action_bus.py`
  - `runner/model_client.py`
  - approved MLPCP Harbor bridge sources under `tracking/variants/...`
- Why: The spec names these as the intended harvest surfaces.

## D-004 — Mandatory `gpt-5.4-mini` delegation

- Date: 2026-06-11
- Decision: Worker delegation is mandatory. The orchestrator must dispatch bounded `gpt-5.4-mini` workers and keep their scopes narrow, guided, and disjoint.
- Why: Principal correction explicitly made mini-worker delegation mandatory and preferred many compact tasks over lane-sized tasks.
- Consequence: Any delegation mechanism failure must be recorded and followed immediately by a fallback delegation attempt.

## D-005 — Hour-0 is frozen before wider lane work

- Date: 2026-06-11
- Decision: The observation envelope schema, the exact 10 tool schemas, and the `loop.py` ↔ `bridge_harbor.py` interface are the Hour-0 contracts. Workers build against `hour0_contracts.md`.
- Why: The build spec marks Hour-0 as blocking and a prerequisite for all later lanes.

## D-006 — Worker mechanism is pinned Codex threads on the main checkout

- Date: 2026-06-11
- Decision: Build workers run as pinned Codex threads, not subagents. They stay in the same checkout on `main/master`, with no worktrees and no branch-based execution.
- Why: Principal correction explicitly required Codex-thread workers and later clarified that all work must stay in the main checkout with no forking/worktrees.
- Consequence: `fork_thread` may be used only in same-directory mode for coordination threads; no git worktree or branch isolation is allowed.

## D-007 — `gpt-5.4-mini` is the default worker model

- Date: 2026-06-11
- Decision: Worker threads default to `gpt-5.4-mini`. `gpt-5.4-mini` may use high or xhigh reasoning when a narrow slice is reasoning-heavy. `gpt-5.4` is reserved for genuinely integration-sensitive or ambiguity-heavy work, and only at low or medium reasoning effort.
- Why: Principal correction set this as the default delegation policy.

## D-008 — Initial subagent dispatch was superseded and shut down

- Date: 2026-06-11
- Decision: The first mini-worker dispatch used `multi_agent_v1.spawn_agent`, but that approach was superseded by principal policy. All five subagents were shut down and replaced with pinned Codex worker threads.
- Why: Principal required thread-based workers only.

## D-009 — Worker threads should use Goal structure plus code review

- Date: 2026-06-11
- Decision: Worker threads should explicitly use Goal structure and the code review skill when available, rather than only reporting that those tools exist.
- Why: Principal preference tightened the worker workflow after the first batch of narrow slices had already started.
- Consequence: Early worker slices that only self-reviewed may need follow-up repair or integration-side review notes.

## D-010 — Runtime surfaces need contract-level review, not only slice-local tests

- Date: 2026-06-11
- Decision: Review executor-facing surfaces such as `prompts.py` as live runtime contracts, not only as narrow worker slices.
- Why: The initial prompts slice was test-green but too thin for the real Aether-2 executor role until a parent/runtime review strengthened `SYSTEM_PROMPT` and ensured the doctrine lines were embedded directly inside it.
- Consequence: Future worker accept/reject decisions should check whether a green slice is still too weak for the actual runtime contract.

## D-011 — Full-spec acceptance, not thin placeholders

- Date: 2026-06-11
- Decision: No slice may be marked accepted or complete if its implementation is knowingly a placeholder for a spec-required behavior.
- Why: Parent audit clarified that the acceptance target is the full Aether-2 file contract in `AETHER2_BUILD_SPEC.md`, not a thinner substitute that only satisfies a narrow smoke or unit test.
- Consequence:
  - Mark such slices as `partial`, `functionally green but spec-incomplete`, or equivalent.
  - Record the exact missing spec requirements in the orchestration ledger.
  - Dispatch an immediate follow-up worker for the missing behavior instead of letting the thin slice stand as complete.

## D-012 — Root cause was under-specified worker packets

- Date: 2026-06-11
- Decision: Treat spec-incomplete worker output primarily as orchestration prompt debt when the worker packet itself was not contract-complete for the assigned component.
- Why: Principal correction clarified that the main failure mode was not worker weakness but under-specified tasks that omitted parts of the component contract.
- Consequence:
  - Every worker task must be contract-complete for its assigned component.
  - Worker packets must include the exact manifest row, required public interfaces, required behaviors, cross-cutting constraints, and the full acceptance checklist for that component.
  - If a worker output is incomplete because the prompt omitted part of the contract, reject or return it as orchestration prompt debt, fix the packet, and re-dispatch.

## D-013 — Return to orchestrator-heavy cadence

- Date: 2026-06-11
- Decision: Direct orchestrator coding is now limited to interface freezes, tiny integration repairs, grouped verification, and final wiring that cannot be safely isolated. Complete components and adversarial contract reviews should be delegated to fresh same-directory Codex threads wherever write scopes are disjoint.
- Why: Parent review confirmed that progress was real but the orchestrator had drifted too far into primary implementation.
- Consequence:
  - Keep jobs/sessions workers running.
  - Dispatch fresh worker threads for remaining complete components and adversarial reviews instead of reusing budget-heavy threads.
  - Reserve `gpt-5.4` medium for the central `loop.py` integration slice after jobs/sessions interfaces stabilize.

## D-014 — Centralize the broken review-helper blocker

- Date: 2026-06-11
- Decision: Stop asking every worker to retry the known-broken `codex-review` helper. Treat the `service_tier` parse failure as one shared blocker until a dedicated diagnosis lane resolves it or establishes the supported alternate gate.
- Why: Repeating the same failing helper invocation burns worker budget without increasing assurance.
- Consequence:
- Workers use the manual review checklist by default for now.
- A dedicated review-gate diagnosis thread owns reproducing/fixing/documenting the helper issue.

## D-015 — VM lifecycle scripts must exist in-tree and be smoke-checked

- Date: 2026-06-11
- Decision: The Aether-2 plan requires `scripts/deallocate_harnesseng_vm.sh` and `scripts/configure_harnesseng_vm_autoshutdown.sh` to be present in the live checkout, executable, and smoke-checked with `--dry-run --help`.
- Why: The spec marks those scripts as required VM lifecycle surfaces, and the live tree inspection showed they were absent despite earlier status assumptions.
- Consequence:
  - Treat any prior "present" claim for those scripts as false-complete until verified in-tree.
  - Record the scripts in the orchestration ledger only after the files exist and the smoke checks pass.

## D-016 — Route-level TPM pacing must be proven, not assumed

- Date: 2026-06-11
- Decision: Aether-2 model-client acceptance requires an explicit test that the route factory enables TPM pacing when the route requests it, plus transient retry and fail-fast behavior for non-transient errors.
- Why: Wrapper-only monkeypatches are not sufficient evidence that the manifest row's pacer path is actually exercised.
- Consequence:
  - Keep the wrapper thin and honest.
  - Prove pacer wiring through `make_model_client_from_route` or an equivalent route-level path.
  - Treat transient retry and non-transient fail-fast as separate contract checks.

## D-017 — Same-directory replacement threads get plain follow-up prompts

- Date: 2026-06-11
- Decision: When replacing a stalled worker by same-directory fork, send the actionable task as a plain prompt to the child thread rather than nesting an extra escaped `<codex_delegation>` wrapper inside the message body.
- Why: W-031 and W-032 initially stalled because the packet was double-wrapped and reached the child as escaped text instead of executable instructions.
- Consequence:
  - Replacement worker threads must receive plain, direct task prompts.
  - If a thread only records setup text and does not start implementation, correct it in-thread immediately before creating yet another replacement.
