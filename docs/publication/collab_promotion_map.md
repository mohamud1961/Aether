# Collab Promotion Map

Status: public-safe curation map

Date: 2026-06-16

This map turns `work/ledger/` into a practical public/private routing guide.
It is intentionally conservative: when a region is mixed, the default is to
sanitize first or keep the raw working material private.

Use this map with the public target namespaces already in the tree:

- `docs/`
- `eval_suite/`
- `variants/`
- `workflows/`
- `tools/`

## Decision Legend

- `promote now by cloning/adapting`: safe to materialize in a public area after
  light cleanup
- `curate as public evidence link only`: keep the source in `work/ledger/`
  and link to it from public docs
- `summarize/sanitize first`: the public shape is clear, but the raw file needs
  redaction or normalization before copying
- `keep private/excluded`: raw working material that should stay out of the
  public tree
- `needs owner/legal/privacy review`: upstream rights or privacy status need an
  explicit decision before public release

## Promote Now

| `work/ledger` region | Public target | Exact artifact type | Why this belongs here |
|---|---|---|---|
| `work/ledger/skills/analyze-agent-runs/` | `workflows/skills/analyze-agent-runs.md` and a small companion note under `docs/research/` | Sanitized workflow skill plus reference notes | The skill logic is generic, the public workflow layer already exists, and the current package is best reused as a cleaned public skill rather than left only in collaboration storage. |
| `work/ledger/aether2_g2_homologs/` | `eval_suite/custom/<family>/`, `eval_suite/boards/`, `eval_suite/scoreboards/` | Synthetic task-pack family, visible prompt, visible verifier, grader, board manifest, example scoreboard | This is the clearest public-safe custom eval family in the collab corpus. The task definitions and deterministic surface are reusable once the run archives stay private. |

## Curate As Public Evidence Link Only

| `work/ledger` region | Public target | Exact artifact type | Why link only |
|---|---|---|---|
| `work/ledger/public_repo_readiness/` | `docs/publication/` | Publication handoffs, inventories, gap list, evidence index, and review receipts | This is the public-ready staging hub, but the working copies should remain here while public docs link to the distilled outputs. |
| `work/ledger/first_result_attribution_mechanism_tournament/` | `docs/research/` or `variants/scoreboards/` | Compact prediction / scoreboard bundle | The bundle is useful as a cited evidence point, but it does not need to be mirrored wholesale into the public tree. |
| `work/ledger/model_led_substrate_v1/` | `docs/research/` | Adversarial review summary and worker audit note | The review artifacts are most useful as a cited source for lessons learned, not as a raw public working tree. |

## Summarize / Sanitize First

| `work/ledger` region | Public target | Exact artifact type | Sanitization note |
|---|---|---|---|
| `work/ledger/stage_02_synthesis/` | `docs/case-studies/`, `docs/research/`, `docs/provenance/` | Redacted case studies, dossier summaries, tracing-readiness note, publication guidance | Export the clean case-study and dossier layers first. Keep the active planning, coverage, and wave folders private. |
| `work/ledger/final_harness_eval_suite/` | `eval_suite/boards/`, `eval_suite/schemas/`, `eval_suite/scoreboards/`, `docs/provenance/` | Board manifests, schema docs, synthetic scoreboard rows, provenance note | Publicize board-level summaries only. Keep `task_packs/`, hidden verifier packs, raw runs, VM pulls, and other evidence bundles private. |
| `work/ledger/aether2_fake_progress_homologs/` | `eval_suite/custom/` or `docs/schemas/` | Homolog manifest example / template | This is a tiny useful example, but it still names internal runner surfaces and should be genericized before public use. |

## Keep Private / Excluded

| `work/ledger` region | Public target | Exact artifact type | Reason to keep private |
|---|---|---|---|
| `work/ledger/aether2_build_orchestration/` and `work/ledger/aether2_build_spec/` | None; distill lessons into `docs/` or `workflows/` instead | Campaign-only orchestration and build-spec notes | These folders contain internal coordination state and path-heavy working notes. |
| `work/ledger/aether2_g5_implementation_orchestration_20260613/`, `work/ledger/aether2_g5_run_analysis_20260613/`, `work/ledger/aether2_run_analysis_20260614/`, `work/ledger/aether2_run_analysis_20260615/` | None | Raw run analysis and orchestration evidence | These are private campaign archives, not public artifacts. |
| `work/ledger/aether2_fake_progress_analysis_20260614/` | None | Analysis scratch space | Keep the working analysis private unless a redacted summary is exported elsewhere. |
| `work/ledger/benchmark_native_certification/`, `work/ledger/certify_first_eval_core/`, `work/ledger/eval_suite_v1_baseline/`, `work/ledger/eval_suite_v1_build/`, `work/ledger/eval_suite_v1_repair_runs/`, `work/ledger/eval_suite_v1_tournament_runs/`, `work/ledger/first_control_route_runs_on_certified_core/`, `work/ledger/model_backed_baseline_on_certified_core/`, `work/ledger/local_iteration_loop_2026-04-06/`, `work/ledger/local_iteration_loop_2026-06-04/`, `work/ledger/stage_03_execution_planning/`, `work/ledger/benchmark_context_pack_20260610/`, `work/ledger/autonomous_loop/` | None | Raw baselines, repair runs, calibration traces, planning packets, or placeholder working state | These are execution archives and scratch surfaces. They are useful internally but should not be mirrored into the public repo. |

## Needs Owner / Legal / Privacy Review

| `work/ledger` region | Public target | Exact artifact type | Review reason |
|---|---|---|---|
| `work/ledger/final_harness_eval_suite/adapter_fixtures/` | `docs/provenance/` only after clearance | Benchmark adapter sample assets | Upstream sample assets can carry redistribution constraints. Clear the rights status before copying any of them into public-facing docs or examples. |

## Practical Next Slice

If we want the safest high-value public expansion order, do it in this sequence:

1. Export the sanitized `trajectory_case_studies/` slice from `work/ledger/stage_02_synthesis/` into `docs/case-studies/`.
2. Export the board-level summaries from `work/ledger/final_harness_eval_suite/` into `eval_suite/boards/` and `eval_suite/scoreboards/`.
3. Sync the generic `analyze-agent-runs` skill into `workflows/skills/`.
4. Keep the run archives, hidden verifiers, and adapter fixtures private until their review gates are closed.

