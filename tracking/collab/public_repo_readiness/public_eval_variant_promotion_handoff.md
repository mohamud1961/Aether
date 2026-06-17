# Public Eval Variant Promotion Handoff

- Status: `COMPLETE`
- Source thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Target thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Date: `2026-06-16`

## Objective And Scope

Promote the strongest public-safe eval-suite and variant-planning substance
out of `tracking/collab/` into the public repo map without leaking private
trajectories, hidden grader internals, private local paths, or contaminated run
artifacts.

Scope:

- inspect the private collab eval and variant planning candidates;
- clone/adapt public-safe artifacts into `eval_suite/`, `variants/`, and
  `docs/`;
- update navigation pages so reviewers can find the promoted material;
- write a public-safe case study plus a concrete handoff note.

Out of scope:

- moving or deleting the private source material in `tracking/collab/`;
- publishing raw trajectories, raw ledger inbox files, hidden grader details,
  eval fixtures, or private local paths;
- creating branches, commits, pushes, worktrees, VMs, containers, or
  eval/full task runs.

## Candidates Inspected

- `tracking/collab/final_harness_eval_suite/`
  - useful for public-safe board, schema, and scoreboard patterns;
  - rejected for direct publication of hidden contracts, raw task packs, and
    private run bundles.
- `tracking/collab/aether2_g2_homologs/`
  - strongest public-safe eval family shape;
  - promoted as a sanitized public homolog contract smoke family.
- `tracking/collab/aether2_fake_progress_homologs/`
  - useful manifest template;
  - adapted into the public homolog contract schema reference and task pack
    shape.
- `tracking/collab/first_result_attribution_mechanism_tournament/`
  - strongest public-safe variant-planning material;
  - promoted as a curated keep/kill decision table and scoreboard summary.
- `tracking/collab/public_repo_readiness/`
  - used for publication guidance and navigation;
  - not copied verbatim when it would expose private path or internal-only
    framing.

## Promoted Public Artifacts

### Eval Suite

- `eval_suite/custom/homolog_contract_smoke/README.md`
- `eval_suite/custom/homolog_contract_smoke/task_pack.json`
- `eval_suite/custom/homolog_contract_smoke/public_homolog_contract_smoke_contract.md`
- `eval_suite/boards/homolog_contract_smoke_v1.json`
- `eval_suite/scoreboards/homolog_contract_smoke_v1.example.scoreboard.json`

### Variant Planning

- `variants/families/attribution_guard_tournament/README.md`
- `variants/families/attribution_guard_tournament/decision_table.json`
- `variants/scoreboards/attribution_guard_tournament_v1.json`
- `variants/shared/decision_rubric.md`

### Public Narrative And Navigation

- `docs/case-studies/attribution-guard-tournament.md`
- `docs/publication/public_evidence_index.md`
- `docs/publication/publication_gap_list.md`
- `README.md`
- `docs/README.md`
- `docs/case-studies/README.md`
- `eval_suite/README.md`
- `eval_suite/custom/README.md`
- `eval_suite/boards/README.md`
- `eval_suite/scoreboards/README.md`
- `eval_suite/schemas/README.md`
- `variants/README.md`
- `variants/families/README.md`
- `variants/shared/README.md`
- `variants/scoreboards/README.md`

## Rejected Or Kept Private

- `hidden_verifier.py` files and `reviewer_pack/` material in the private eval
  suite;
- raw run folders, trace bundles, and workspaces under `tracking/collab/`;
- eval row copies, official fixture internals, and private local paths;
- any claim of production readiness, eval leadership, or universal
  public-runnability.

## Validation

- path/link existence checks on the new public docs and artifact references:
  - passed
- `rg` sweeps over changed public files for `/Users/mohamud`, `/private/tmp`,
  `file:///Users`, secrets-like tokens, `hidden grader`, raw trajectory claims,
  stale MIT claims, and production/eval leadership claims:
  - passed
- `git diff --check` over the touched files:
  - passed
- JSON parse checks for the new public JSON artifacts:
  - passed
- `python3 tools/aether2_genericity_check.py`:
  - passed

## Outcome

The public surface now has:

- a second concrete public eval family beyond the initial smoke pack;
- a public homolog schema/task-pack example that stays synthetic and
  eval-free;
- a public variant keep/kill tournament summary with an explicit non-promotion
  outcome for the sentinel-failing winner;
- a case study and index links that make the promoted material discoverable.

## Exact Next Slice

Publish one more public-safe variant family or eval family with a different
failure pressure than the homolog contract smoke family, then add a matching
case study and scoreboard view so the public map shows a broader range of
shapes without touching private evidence.

## External-State Confirmation

- No branch, commit, push, worktree, VM, container, or eval/full task run
  was created.
- No server or background process was started for this slice.
- No external state remains intentionally active.

## RAW_LEDGER_UPDATE

- Persisted: yes
- Private raw historian input path:
  `tracking/ledger/inbox/2026-06-16/122029_codex_public-repo-readiness-eval-variant-promotion-slice_18ef083cd9.md`

## Thread Send

- Target thread ID: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Tool/mechanism: `codex_app.send_message_to_thread`
- Result: success
