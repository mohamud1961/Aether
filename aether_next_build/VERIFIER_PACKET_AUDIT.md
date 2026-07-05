Verifier Packet Hardening Audit

Date: 2026-06-29
Slice: verifier packet / success-definition hardening

Implemented

- `RuntimeConfigIR` now carries `success_definition` and `local_verification_limits`.
- `CompiledRuntime` now carries `solver_identity_prompt`, `success_definition`, and `local_verification_limits`.
- Workbench compilation preserves architect `success_definition` and `local_verification_limits` as explicit runtime metadata instead of only folding them into advisory text.
- Contract compilation preserves `success_definition` when present.
- Verifier packets now expose first-class fields for:
  - `success_definition`;
  - `local_verification_limits` as structured `{source, statement}` entries;
  - `solver_system_prompt` with rendered text, summary, and prompt hash;
  - `config_realization` summary with architect path, visible/runtime-allowed tools, context policy, verification policy, and workbench repair metadata when present;
  - `official_grader_authority`, which remains `external_benchmark`.

Evidence Source

- Packet builder now prefers the latest `config_realization` receipt and falls back to compiled runtime metadata when no receipt-local override exists.
- Workbench-specific repair warnings and rejected config items still come from the kernel-recorded config realization receipt.

Behavior Preserved

- Deterministic checks, artifact evidence, obligations, active verifier findings, and recent receipts remain in the verifier packet.
- Completion gating behavior is unchanged: `completed` allows kernel completion and `needs_repair` still blocks completion through the existing verifier result path.

Known Limits

- `success_definition` is now verifier-visible metadata, but it is not yet compiled into a separate deterministic completion rule.
- `local_verification_limits` remain architect/runtime advisories; they do not independently alter deterministic checks.
