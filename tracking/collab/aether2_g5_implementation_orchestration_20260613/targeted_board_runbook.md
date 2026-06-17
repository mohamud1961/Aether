# Targeted Board Runbook

This directory holds the preregistration material for the fast targeted board
described in `IMPLEMENTATION_PLAN.md` R5.

## Scope

- The board is preregistered only.
- The board is not executed in this patch.
- The helper in `tools/aether2_targeted_board.py` validates the manifest and
  scheduler policy.
- The checked-in example manifest is
  `targeted_board_manifest.example.json`.

## Board Contract

- Maximum of ten tasks.
- Each task records:
  - failure family;
  - reason selected;
  - expected capability pressure;
  - baseline evidence;
  - predicted change;
  - named sentinels;
  - resource class;
  - timeout;
  - contamination controls.
- Scheduler policy records:
  - no more than three light containers concurrently;
  - one heavy build at a time;
  - one QEMU or service-sensitive task at a time;
  - disk-pressure and process-pressure preflight;
  - cleanup only for attributable resources;
  - immutable output directories per task and attempt.

## Execution Posture

The board remains in preregistration mode until the integration gate authorizes
execution. This runbook does not launch tasks, mutate a corpus, or create real
board output.

## Stop Conditions

- Do not run the board from this directory.
- Do not treat this preregistration bundle as score evidence.
- Revalidate the manifest if any task, sentinel, or scheduler limit changes.
