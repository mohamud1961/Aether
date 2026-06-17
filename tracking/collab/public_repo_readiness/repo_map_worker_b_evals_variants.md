# Repo Map: Evals, Variants, Evals, and Public Readiness

## Executive Summary

- The repo currently has a strong internal evaluation stack, but the publishable surface should be much smaller than the working tree. The safest public core is `evals/`, a sanitized `eval_suite/` subtree, a small `variants/` family tree, and generic harness tools.
- `official_tasks/` is a eval corpus, not a public showcase tree. It contains 90 task directories and many embedded assets that look proprietary, sensitive, or license-encumbered. Keep it private unless each task is individually cleared.
- `tracking/variants/` is almost entirely raw execution material: tarballs, host receipts, logs, trial traces, and ad hoc analysis notes. It should stay private.
- The best public custom eval family found here is `tracking/collab/aether2_g2_homologs/`, but only the task definitions and sanitized summaries, not the run outputs or evidence tarballs.
- The `tracking/collab/final_harness_eval_suite/` board is real and useful, but its task packs, hidden truths, and run folders are mostly private. Publicize board-level manifests and sanitized scoreboards only.
- Variant packaging should be family-level for public release, harness-level for shared utilities, and experiment-level only for internal run logs.

## Inventory By Folder

| Folder | Observed contents | Classification | Public recommendation | Notes |
|---|---|---|---|---|
| `evals/` | `verification_eval.py`, `step_efficiency_eval.py`, `context_eval.py`, README | Public eval suite core scaffold | Yes, as the home for generic eval contracts and metrics | Currently just lightweight stubs, but they are the right public landing zone for real eval definitions. |
| `experiments/` | one example config, one placeholder scoreboard, empty runs dir | Public experiment scaffold | Yes, but only as experimental config/examples | Keep it clearly separate from certified eval evidence. The current scoreboard is a stub, not proof. |
| `variants/` | absent at top level | Missing public tree | Create a small public `variants/` tree | The only live variant tree is under `tracking/variants/`, which is private. |
| `tracking/variants/` | `mlpcp_v2`, `mlpcp_v3`, tarballs, host receipts, logs, trial artifacts, pause note | Private raw run/artifact/workspace | Keep private | This is execution evidence, not a publishable tree. It includes raw receipts and replayable traces. |
| `tracking/collab/final_harness_eval_suite/` | board manifests, schemas, task packs, fixtures, runs, scoreboards, provenance docs | Mixed, mostly private | Split: public board summaries, private task packs and runs | The board is real and valuable, but hidden truths and raw rows should not be public. |
| `tracking/collab/final_harness_eval_suite/task_packs/` | hard rows, sentinel rows, composition rows, hidden verifiers, ceiling/known_bad, fixtures | Private pressure-family and original-private eval assets | Keep private; publish only sanitized briefs if needed | Several rows are explicit hidden-contract stress tests, so full packs are too revealing. |
| `tracking/collab/final_harness_eval_suite/runs/` | result rows, scoreboards, invalidity and contamination reports, traces, artifact bundles | Private run-output bundle | Keep private; export sanitized scorecards only | The run folders contain absolute host paths and raw evidence refs. |
| `tracking/collab/final_harness_eval_suite/official_eval_family_board.yaml` | tool-call composite, tool-call atom suite, retrieval-context suite, filesystem-agent suite, terminal-workflow calibration rows | Public calibration board candidate | Yes, if treated as non-certifying audit surface | Good for public calibration, not for promotion authority. |
| `tracking/collab/final_harness_eval_suite/terminal_workflow_challenge_lane.yaml` | 2 official challenge rows | Public calibration board candidate | Yes, if kept explicitly non-certifying | This is a narrow official eval lane, useful for audit but not for inner-loop optimization. |
| `tracking/collab/final_harness_eval_suite/final_suite_registry.yaml` and related registry docs | full board shape, provenance, contamination policy | Internal governance docs | Public only after heavy sanitization | Current versions expose internal row ids, hidden-contract notes, and provenance text that should stay internal. |
| `tracking/collab/aether2_g2_homologs/` | 5 synthetic homolog tasks, instructions, verifiers, dockerfile, tarballs, run results | Public custom behavioral eval family candidate | Publish the task family; keep tarballs and runs private | This is the strongest “good enough to show” custom eval family in the tree. |
| `tracking/collab/aether2_fake_progress_homologs/` | example homolog manifest, no scored run bundle | Public-facing template candidate, not evidence | Optional public example, but not necessary | It is eval-neutral and useful as a template, but it is more of a manifest example than a real scored suite. |
| `tracking/collab/aether2_g5_implementation_orchestration_20260613/` | preregistered targeted board example, implementation plan, handoffs, audit docs | Private preregistration / orchestration workspace | Keep private | These are research-process artifacts, not public eval assets. |
| `tracking/collab/aether2_g5_run_analysis_20260613/` | frozen analysis bundle, normalized rows, scoreboards, prediction audit, lane recommendation | Private analysis evidence bundle | Keep private | Valuable internally, but too raw and too tied to a specific failure analysis to publish as a public asset. |
| `tracking/collab/aether2_run_analysis_20260615/` | targeted run rows, artifacts, environment contracts, logs, scoreboards | Private raw run bundle | Keep private | The row names are useful internally, but the bundle is not public-ready. |
| `tracking/collab/aether2_g2_homologs/runs/` | result rows, scoreboards, verifier context, workspaces | Private raw run evidence | Keep private | Only the sanitized summary row data should be public, not the live workspaces or tarballs. |
| `official_tasks/` | 90 eval task directories with instructions, env assets, solutions, tests, data files | Eval corpus/private/ignore | Keep private by default | This is the biggest licensing and contamination risk surface in the repo. |
| `tasks/` | task registry and README | Public loader/registry scaffold | Yes, but not as the eval corpus itself | This is a fine public interface layer; the actual corpus should not be conflated with it. |
| `tools/` | generic board renderers plus Aether-2 specific runners and checks | Mixed harness utilities | Public generic tools, keep Aether-2-specific tools internal | `render_final_harness_scoreboard.py` and generic validators are publishable; `aether2_*` runners should stay internal unless renamed and scrubbed. |
| `tracking/collab/stage_02_synthesis/` | eval inventory docs and dossiers | Internal synthesis notes | Keep private | These are evidence-gathering notes, not a public artifact surface. |

## What Should Be Public

- `evals/` as the public home for generic evaluation contracts, metrics, and score adapters.
- A sanitized `eval_suite/` tree with board manifests, schemas, and curated score summaries.
- A family-level `variants/` tree containing only genericized or sanitized variant families.
- The `aether2_g2_homologs` task family, after removing evidence tarballs, raw run outputs, and host-specific artifacts.
- Board-level calibration surfaces like `official_eval_family_board.yaml` and `terminal_workflow_challenge_lane.yaml`, clearly labeled as audit/calibration only.
- Generic harness utilities in `tools/` that do not encode task-specific or eval-specific knowledge.

## What Should Stay Hidden

- Any `hidden_truth.json`, `hidden_verifier.py`, or `reviewer_pack/` content.
- Any `tracking/variants/**/runs/**`, `trial.log`, `verifier_context`, `host_receipts`, or tar.gz evidence bundles.
- Any `tracking/collab/final_harness_eval_suite/task_packs/**` that contain hidden-contract stress tests or pressure-family target specifics.
- The `official_tasks/` corpus as a whole, unless each task is individually cleared for release.
- Internal synthesis dossiers and run-analysis bundles under `tracking/collab/aether2_g5_*` and `tracking/collab/aether2_run_analysis_*`.

## Recommended Target Public Tree

```text
eval_suite/
  README.md
  boards/
    final_suite_registry.yaml
    official_eval_family_board.yaml
    sentinel_composition_board.yaml
    terminal_workflow_challenge_lane.yaml
  schemas/
    *.schema.yaml
  task_packs/
    public/
      aether2_g2_homologs/
        family.yaml
        g2_01_file_artifact/
        g2_02_service_survives_exit/
        g2_03_interactive_session/
        g2_04_package_install/
        g2_05_long_running_job/
  scoreboards/
    curated/
      *.md
      *.json
  evidence/
    curated/
      sanitized_result_rows.jsonl
      sanitized_row_samples.json
  adapters/
    tool_call_composite/
    retrieval_context/
    filesystem_agent/
  docs/
    publication_policy.md
    contamination_policy.md

variants/
  README.md
  aether2/
    family.yaml
    curated_evidence/
    scoreboard/
  terminal_workflow/
    calibration/
```

## Curated Evidence Candidates

- `tracking/collab/final_harness_eval_suite/runs/20260530T154755Z/scoreboard.md`
- `tracking/collab/final_harness_eval_suite/runs/20260530T154755Z/result_rows.jsonl`
- `tracking/collab/final_harness_eval_suite/runs/20260530T154755Z/result_rows_scoreboard.json`
- `tracking/collab/final_harness_eval_suite/official_eval_family_board.yaml`
- `tracking/collab/final_harness_eval_suite/terminal_workflow_challenge_lane.yaml`
- `tracking/collab/aether2_g2_homologs/pre_g3_ready_handoff_20260612.md` only as an internal handoff, not as public evidence
- `tracking/collab/aether2_g2_homologs/runs/20260612T185102Z/scoreboard.md` after redaction, if a public synthetic homolog scoreboard is desired
- `tracking/collab/aether2_g2_homologs/runs/20260612T185102Z/result_rows.jsonl` after redaction, if row-level evidence is needed

## Migration Risks And Open Questions

- `official_tasks/` has no top-level license file in the scan I ran, and it contains many assets that are plausibly proprietary, third-party, or otherwise redistribution-sensitive. Examples include database dumps, OS install media references, model weights, image/PDF assets, and git history/secrets tasks.
- Several eval-adjacent fixtures in `tracking/collab/final_harness_eval_suite/adapter_fixtures/` may have upstream redistribution constraints. tool-call composite, retrieval-context suite, and filesystem-agent suite samples should be reviewed before any public mirror.
- The current final-suite board manifests expose internal row ids and hidden-contract notes. Those are fine internally, but a public board should use genericized family names and avoid hidden truth hints.
- Publicizing raw run folders would leak absolute host paths, row-specific artifact paths, and internal failure notes. That would make the public repo noisier and more revealing than necessary.
- The cleanest public story is family-level, not run-level: publish the task family, the visible verifier, the deterministic grader, and a small sanitized scoreboard.
- Open decision: whether the public tree should include any pressure-family custom rows beyond audit/calibration lanes. My recommendation is no, except as a narrow non-certifying calibration surface.
- Open decision: whether `aether2_g2_homologs` should retain Aether-2 branding or be genericized. For a public repo, generic family names are safer.

## Bottom Line

- Public: `evals/`, generic `tools/`, sanitized `eval_suite/`, and family-level custom homologs.
- Private: `official_tasks/`, `tracking/variants/`, raw run folders, hidden truth packs, and internal analysis bundles.
- Mixed: `tracking/collab/final_harness_eval_suite/` should be split into public calibration manifests and private task/run evidence.
