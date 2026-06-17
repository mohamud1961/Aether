# Whole-Harness Variants

Whole-harness stack, route, and recipe-level variants.

This lane captures the harness as a whole rather than a single mechanism family.
It includes historical code snapshots for the kernel line and the MLPCP v3 line,
plus the decision history and backlog.

**SNAPSHOT NOTICE**: All files under `kernel_line/code/` and `mlpcp_v3/code/` are
historical code snapshots. They reference `runner.*` imports and are not
standalone-runnable outside the repo. They are preserved as readable records of
the architecture at each phase. The live, runnable harness is `harness/aether2`,
which supersedes both lines documented here.

## Harness Lines

### Kernel line (Phases 0–6) — `kernel_line/code/`

This is the **complete** kernel module set (19 modules, ~10.5k lines) — the entire
prior whole-harness line, not an excerpt:

- `active_evidence_kernel.py` (1844) — the Phase-1 kernel entrypoint, composing all
  `kernel_*` modules below (receipts, gates, recovery, compaction, control-plane,
  state, services, interrupts, working-window, success-contract, layer-2 audit, …).
- `evidence_kernel.py` (660) — the narrower Phase-0/1 predecessor.
- `packet04_route_manifest.py` (2122) — the route manifest that drives variant
  selection (self-contained registry).
- `kernel_control_plane.py`, `kernel_state.py`, `kernel_gates.py`,
  `kernel_recovery.py`, `kernel_compaction.py`, `kernel_working_window.py`,
  `kernel_context_pack.py`, `kernel_receipts.py`, `kernel_evidence_trail.py`,
  `kernel_services.py`, `kernel_interrupts.py`, `kernel_native_tools.py`,
  `kernel_success_contract.py`, `kernel_layer2_audit.py`, `kernel_artifacts.py`,
  `kernel_tpm_pacer.py` — the supporting kernel subsystem.

Lineage note: a few base utilities this line depends on (`model_client`/route
schemas, `action_bus`, the artifact/pacer helpers) were carried forward into — and
now live in — `harness/aether2`, since the current runtime descends from this line.
`kernel_artifacts.py` and `kernel_tpm_pacer.py` here are the original kernel-era
copies, reproduced for a complete record.

### MLPCP v3 line (Phase 7 — paused)

- `mlpcp_v3/` — the MLPCP v2/v3 harbor cockpit architecture.
  `mlpcp_v3/code/lean_cockpit.py` (735 lines) is self-contained.
  Other files import the purged `runner.mlpcp_v2.*` sub-package and cannot run.
  See `mlpcp_v3/README.md` and `mlpcp_v3/pause_state.md`.

### Aether-2 line (current winning line)

`harness/aether2/` is the live harness — see `../aether/README.md` for summary.

## Other Artifacts

- `decision_history.md`: Phase 0–7 chronological history with honest failures.
- `variant_hypothesis_backlog.md`: H1–H8 backlog from the G5 run analysis.
- `../scoreboards/whole_harness_stack_summary_v1.yaml`: stack posture summary.
- `../shared/lineage_map.md`: route / stack lineage map.

## Status

This lane is a historical snapshot and decision record, not a benchmark-readiness
claim. No harness line has been promoted to eval-suite winner status.
The live harness is `harness/aether2`.
