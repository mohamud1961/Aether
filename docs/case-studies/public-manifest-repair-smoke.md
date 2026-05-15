# Public Manifest Repair Smoke Case Study

Status: public-safe case study

This page shows a second public engineering shape for HarnessEng: a synthetic
eval-pack slice with a deterministic grader, a board manifest, and an example
scoreboard. It is intentionally different from the Aether migration and
runtime capability migration case study. Instead of proving a namespace migration or adding
story, it shows how the repo packages a small verifier-repair eval without
leaking private run histories or evaluation-sensitive materials.

## Problem And Context

The public story needed more than one engineering shape.

The first case study demonstrates namespace and runtime capability work. This one
demonstrates the eval-first packaging side of the repo:

- a synthetic filesystem repair task;
- a messy workspace fixture with decoy files;
- a deterministic local grader;
- a board manifest and example scoreboard;
- public-safe wording that stays explicit about what is not being claimed.

## Engineering Loop Used

The loop here was eval-first and deliberately narrow:

1. classify the slice as a public eval-pack creation task;
2. define a bounded task contract with a messy workspace and clean reference;
3. implement a deterministic grader and the board/scoreboard wiring;
4. keep the admission level diagnostic and the contamination policy clean;
5. validate the docs and public indexes with path checks and overclaim sweeps;
6. keep the slice only because the evidence stayed synthetic and public-safe.

## Public Artifacts Produced

- `eval_suite/custom/public_manifest_repair_smoke/README.md`
- `eval_suite/custom/public_manifest_repair_smoke/task_pack.json`
- `eval_suite/custom/public_manifest_repair_smoke/grader.py`
- `eval_suite/boards/public_manifest_repair_smoke_v1.json`
- `eval_suite/scoreboards/public_manifest_repair_smoke_v1.example.scoreboard.json`
- `tools/run_public_manifest_repair_smoke.py`
- `tests/test_public_manifest_repair_smoke.py`
- `tracking/collab/public_repo_readiness/public_eval_pack_handoff.md`

## Evidence Table

| Artifact | What it shows |
| --- | --- |
| `eval_suite/custom/public_manifest_repair_smoke/README.md` | A small public-safe smoke pack built around a synthetic filesystem repair task. |
| `eval_suite/custom/public_manifest_repair_smoke/task_pack.json` | A bounded diagnostic contract with a clean contamination policy and no public evaluation row. |
| `eval_suite/custom/public_manifest_repair_smoke/grader.py` | Deterministic manifest, summary, and checksum grading. |
| `eval_suite/boards/public_manifest_repair_smoke_v1.json` | Board wiring to the pack, grader, fixture root, and smoke runner. |
| `eval_suite/scoreboards/public_manifest_repair_smoke_v1.example.scoreboard.json` | Example scoreboard with one pass row and one fail row, labeled as smoke/example output. |
| `tracking/collab/public_repo_readiness/public_eval_pack_handoff.md` | Review, validation, and out-of-scope notes for the slice. |

## Validation Summary

| Check | Result |
| --- | --- |
| Path existence checks for changed docs | passed |
| `rg` sweeps for machine-local path leaks | passed |
| `rg` sweeps for stale MIT wording and overclaims | passed |
| `git diff --check` | passed |
| `python3 tools/aether2_genericity_check.py` | passed |

## What Remains Out Of Scope

- evaluation-grade claims or leadership claims;
- production-scale release claims or public-demo claims;
- run histories, raw ledgers, or grader internals;
- official evaluation fixtures or copied evaluation rows;
- broader eval-suite expansion beyond the smoke example documented here.

## Privacy And Provenance Boundaries

The slice is wholly synthetic and locally authored. It uses no credentials, no
external services, and no private evidence in the public narrative.

The public docs intentionally stay at the level of:

- the task contract;
- the deterministic grader shape;
- the board and scoreboard artifacts;
- the validation results and review summary.

They do not expose hidden verifier internals, raw traces, or private
publication artifacts.

## Public Evidence Links

- `README.md`
- `docs/README.md`
- `docs/case-studies/README.md`
- `workflows/ai-native-engineering-operating-system.md`
- `tracking/collab/public_repo_readiness/public_eval_pack_handoff.md`
- `eval_suite/custom/public_manifest_repair_smoke/README.md`
- `eval_suite/custom/public_manifest_repair_smoke/task_pack.json`
- `eval_suite/custom/public_manifest_repair_smoke/grader.py`
