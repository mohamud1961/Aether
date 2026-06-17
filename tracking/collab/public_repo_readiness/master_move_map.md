# Master Move-Map & Execution Plan (authoritative)

Status: `READY_TO_EXECUTE` — Date: 2026-06-16
Synthesizes: `move_map_eval_suite.md`, `move_map_variants.md`, `move_map_workflows.md`,
`move_map_research_docs.md`, `aether2_import_safety_and_baseline.md`.

Role target: **Bolder Apps — Agentic Engineer (Claude Code)**: "orchestrate the agents,
design the skills, manage context and memory, ship working apps." Headline = the
**methodology** (loop engineering, skills, orchestration) backed by a **real runtime**,
**real evals**, **real variants**, and **real research**.

Operating rules (from user): nothing is built new — discover, move, sanitize, organize.
`harness/aether2` must stay green (gate: 302 tests pass). Work on `main`, no push.

---

## 1. Final public tree (target)

```
harnesseng/
  README.md  START_HERE.md  ARCHITECTURE.md  (root product docs)
  harness/          # the agent runtime (self-contained; no runner/ imports)
    aether2/{runtime,control,tools,skills,hooks,agents,env,monitoring,verification,traces,cli}
    tools/          # genericity_check, targeted_board, scoreboard
  eval_suite/
    custom/families/<6 families>/   custom/harness/   # custom: family + whole-harness
    pressure_family/<neutral families>/             # names stripped, hidden verifiers excluded
    graders/  schemas/  boards/  scoreboards/  fixtures/  sentinels/
  variants/
    families/<mechanism families>/  # family-level (code snapshots + cards + scoreboards)
    harness/        # whole-harness lines: kernel line, mlpcp_v3 (snapshots + decision_history)
    shared/  scoreboards/
  workflows/        # THE showcase
    loop-engineering/  skills/  orchestration/  synthesis/  prompts/  templates/  schemas/
  research/
    synthesis/  case_studies/  phases/  methodology/
  docs/
    architecture/  case-studies/  provenance/  publication/
  tests/
    harness/{runtime,control,tools,env,verification,traces,monitoring,integration}
    eval_suite/  variants/  workflows/
  scripts/  pyproject.toml  .gitignore  LICENSE
```

## 2. EXCLUDE (gitignore — kept locally, never published)

`official_tasks/` · `tracking/` (extract first, then exclude) · `blocks/` (variant source already
copied into `variants/`) · `runner/` legacy (everything except the 6 aether2-closure modules,
which move into `harness/`; kernels snapshot into `variants/harness/`) · `evals/` (3 stubs) ·
`prompts/` originals (sanitized copies go to `workflows/prompts/`) · `website/` ·
`mlpcp_v2_complete_variant_package_expanded_docs/` · `p4r1/` `p4r2/` (only .DS_Store) ·
`scratch/` `yaml/` `output/` `repomix-output.xml` · venvs/caches · `eval_suite/attempts/`
(host-path raw runs) · all `reviewer_pack/`, `hidden_*.json`, `hidden_verifier.py`, raw `**/runs/`.

## 3. The 6 runner modules aether2 needs (Slice 1 — me, critical path)

Move into `harness/aether2/runtime/` (or `traces/`): `model_client.py`, `schemas.py`,
`kernel_tpm_pacer.py`, `action_bus.py`. Extract 3 helpers (`_clean_hidden_refs` →
traces redaction util; `_sha256_file`,`build_artifact_record` → `traces/artifacts.py`) so the
full `kernel_layer2_audit.py`/`kernel_artifacts.py` can leave for `variants/harness/`.
After: `grep -rn "import runner" harness/` must be **empty**; 302 tests green; fix the 1
pre-existing `action_bus` failure as a quality win.

## 4. Showcase set (what leads)

- **Workflows (headline):** `loop-engineering/` (sanitized orchestration ledger = 32-worker build,
  hour-0 contracts, run-analysis case study); the deep-synthesis skill family + the 15 role prompts;
  loop-orchestrator, analyze-agent-runs (merged full version), eval-first-implementation-slice.
- **Harness:** `aether2` runtime (loop 2634 LOC, delta 2099, verify 1202, decision_trace 1380).
- **Eval suite:** 6 self-contained custom evals (manifest-repair, mcp-registry, subagent-handoff,
  skill-loader, runtime-policy-hook, homolog-contract) + 5 G2 homologs; pressure-family families
  fhard_02 (service orchestration) + fhard_06 (repo recovery, self-contained 195-line grader).
- **Variants:** attribution_guard_tournament (only fully-scored: prediction→comparison→keep/kill);
  finalization_truth_family (adversarial review found+fixed a dead-code bug; 7/7 tests);
  whole-harness: active_evidence_kernel line + mlpcp_v3 lean_cockpit; `decision_history.md` (Phase 0–7).
- **Research:** failure-taxonomy + mechanism-map (multi-wave), BigAI trace layer (312 runs),
  10 trajectory case studies, the 4-phase stages narrative.

## 5. Sanitization list (required before publish)

- 15 `prompts/*` line-3 `/Users/mohamud/...` → generic `<project>/`.
- Run-analysis & accepted_claims docs: strip `/Users/mohamud/`, `/home/azureuser/` (research-docs map §6, items flagged YES).
- Source-system dossiers + trajectory case studies: convert private `research/sources/...`
  `evidence_paths:` to `[private-source: <label>]`.
- Eval names → neutral (see per-map tables): `fsent_01_tool_call_tool_call_composite_composite`→`..._composite`;
  `fhard_0x` → neutral cluster names; `terminal_workflow_verifier_repair/`→`verifier_repair/`;
  `source_eval_family: retrieval_extraction_hard_row`→`pressure_family_retrieval_extraction`;
  AGENTS.md derivative strips Azure/terminal-workflow/tool-call composite.

## 6. Decisions taken (defaults; override if wrong)

1. **`blocks/` excluded** — variant families already carry their code copies; `variants/` is a
   curated snapshot gallery (snapshots needn't run standalone; documented as such).
2. **Eval *adapters* (tool-call composite/filesystem-agent suite/etc. corpus integrations) excluded** — can't run without
   corpora + drag a 12-module `runner/` chain. "Eval-derived" = the fhard/fsent task packs
   (included, names stripped). `eval_suite/adapters/README.md` documents this.
3. **`eval_suite/custom` canonical = `families/` + `harness/`** (drop flat duplicates; repoint boards).
4. **Whole-harness variants = snapshots** (kernel line, mlpcp_v3). Old kernel tests stay private with `runner/`.
5. **Empty variant families**: populate the ones with real `blocks/` code + Phase evidence
   (`filesystem_open_workflow`, `verifier_repair`, `dependency_config_environment`); drop
   `long_horizon_artifact_handoff` (no clean single code unit) — narrate it in `decision_history.md`.
6. **Hidden verifiers / corpora / raw runs**: never published.

## 7. Execution sequence

| # | Slice | Owner | Gate |
|---|---|---|---|
| 1 | Harness self-containment (move 6 modules, extract helpers, fix action_bus) | me | `grep import runner harness/`=∅; 302 green |
| 2 | Workflows: prompts→sanitize, governance/schemas, loop-engineering/, merge skills, derived skills | agent W | no host paths; links resolve |
| 3 | Research+docs: synthesis/case-studies/phases/methodology move+sanitize; fill docs/ | agent R | no host paths/private source paths |
| 4 | Eval suite: flatten custom; consolidate pressure_family (strip names, drop hidden verifiers); move generic schemas; fix boards | agent E | graders self-contained; no eval names; no hidden truth |
| 5 | Variants: assemble gallery; populate empty families from blocks; kernel+mlpcp snapshots→harness/; dedupe scoreboards; strip names | agent V | no eval names; snapshots documented |
| 6 | Exclusions: `.gitignore` (blocks, runner legacy, tracking, official_tasks, website, …); remove p4r1/p4r2 | me | clean `git status`; no private paths staged |
| 7 | Tests: categorize into folders mirroring tree; quarantine 28 legacy-collection tests with their excluded source | me | full suite collects; aether2 green |
| 8 | Root docs (README/START_HERE/ARCHITECTURE) + commit in logical slices on main | me | clean-tree sanity |

Agents W/R/E/V run scoped to their own top-level dir only — no edits to `harness/`, `runner/`,
`.gitignore`, or cross-imported `.py`. I review each git diff before the next slice and commit per area.
