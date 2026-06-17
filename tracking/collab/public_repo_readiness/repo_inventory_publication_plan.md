# Public Repo Readiness Inventory and Publication Plan

Scope: repo-root inventory snapshot

Read-only inventory completed against the repo root, `runner/aether2/`, `tools/`, `tests/`, `evals/`, `experiments/`, `tracking/collab/`, `research/`, `prompts/`, `blocks/`, `runner/` legacy surfaces, `scripts/`, and `website/`.

## Executive Summary

This repository is already strong enough to become a credible open-source research-product portfolio, but not as a single undifferentiated tree.

The right public release shape is:

- a thin, production-grade harness core;
- a clean eval substrate;
- curated research notes and case studies;
- a public variant gallery with scoreboards;
- a small amount of sanitized historical evidence;
- no raw trajectories, VM pulls, caches, private ledgers, or vendored environments.

The current tree mixes those layers together. The main job before publication is separation, not invention.

## Top-Level Inventory

Legend: `public core`, `public docs/research curated`, `public examples/evidence curated`, `private/ignore`, `legacy/archive`, `needs decision`.

| Top-level path | Class | Publication note |
|---|---|---|
| `.DS_Store` | private/ignore | Mac metadata; remove everywhere. |
| `.git` | private/ignore | Repository internals; not part of a public artifact. |
| `.gitignore` | public core | Keep. It already blocks key noise like caches and `repomix-output.xml`. |
| `.pytest_cache` | private/ignore | Test cache; remove. |
| `.venv` | private/ignore | Local environment; do not publish. |
| `AGENTS.md` | needs decision | Current content is too internal and operational; split into public contributor guidance and private operator notes. |
| `FAILURE_CARD_SCHEMA.md` | public docs/research curated | Good candidate for public research/process docs. |
| `GOVERNED_MULTI_AGENT_OPERATING_MODEL.md` | public docs/research curated | Useful if sanitized; move private governance detail out. |
| `MECHANISM_CARD_SCHEMA.md` | public docs/research curated | Good public research artifact. |
| `PRINCIPAL_AGENT_WORKFLOW.md` | public docs/research curated | Keep if rewritten as a public workflow reference. |
| `README.md` | public core | Main public entrypoint. |
| `SYNTHESIS_PREP_CHECKLIST.md` | public docs/research curated | Useful as a public research-process reference. |
| `SYNTHESIS_TEAM_SPEC.md` | public docs/research curated | Keep if the wording is sanitized. |
| `TRAJECTORY_SOURCE_CASE_STUDY_TEMPLATE.md` | public docs/research curated | Strong candidate for case-study scaffolding. |
| `VARIANT_FAMILY_SEED_SCHEMA.md` | public docs/research curated | Good public schema for variant packaging. |
| `blocks` | public core | Core harness "lego block" library. |
| `evals` | public core | Thin right now, but clearly part of the public substrate. |
| `experiments` | public docs/research curated | Public-facing experiment configs and scoreboards, not raw runs. |
| `mlpcp_v2_complete_variant_package_expanded_docs` | legacy/archive | Old variant package docs snapshot; archive or distill. |
| `official_tasks` | private/ignore | Eval corpus and task data; keep out of the public repo entirely. |
| `p4r1` | legacy/archive | Placeholder/obsolete artifact. |
| `p4r2` | legacy/archive | Placeholder/obsolete artifact. |
| `prompts` | public core | Public prompt assets and role docs, after sanitization. |
| `pyproject.toml` | public core | Keep. |
| `repomix-output.xml` | private/ignore | Generated bundle; remove from public release. |
| `research` | needs decision | Mixed curated research and raw source dumps; split it. |
| `runner` | needs decision | Mixed active core plus old runner lines; split current core from archive. |
| `scratch` | private/ignore | Ephemeral and likely noisy. |
| `scripts` | public core | Public launcher and maintenance scripts, with cleanup of eval-specific defaults. |
| `tasks` | private/ignore | Likely pressure-family task corpus; keep out of the public repo. |
| `tests` | public core | Strong public verification surface. |
| `tools` | public core | Core diagnostics/orchestration tooling, but some scripts are eval-specific and need review. |
| `tracking` | private/ignore | Raw history, runs, VM pulls, and private collaboration state should not ship; curate only exported docs into `docs/` or `variants/`. |
| `venv` | private/ignore | Local environment; do not publish. |
| `website` | public core | Public site should ship, but its build artifacts and internal agent docs should not. |
| `yaml` | private/ignore | Currently only cache/bytecode noise. |

## Key Area Findings

### `runner/aether2/`

This is the cleanest and most public-ready core in the repo.

Representative modules and roles:

- `runner/aether2/bridge_harbor.py` - task mounting and runtime wiring.
- `runner/aether2/context.py` - prefix transcript management.
- `runner/aether2/delta.py` - workspace delta snapshots and evidence ledger helpers.
- `runner/aether2/envelope.py` - typed observation envelopes.
- `runner/aether2/executor.py` - workspace-scoped foreground execution.
- `runner/aether2/jobs.py` - detached job registry.
- `runner/aether2/loop.py` - continuous execution loop.
- `runner/aether2/metrics.py` - scorecards and action breakdowns.
- `runner/aether2/mirror.py` - progress mirror.
- `runner/aether2/model_client.py` - provider wrapper.
- `runner/aether2/orientation.py` - environment probe and contract snapshot.
- `runner/aether2/prompts.py` - prompt source of truth.
- `runner/aether2/receipts.py` - model-invisible receipt capture.
- `runner/aether2/sessions.py` - tmux-backed session registry.
- `runner/aether2/tools.py` - native tool schemas and dispatch.
- `runner/aether2/verify.py` - fresh-context verification and replay checks.

What this means for publication:

- Keep this as the public harness kernel.
- Move any eval-specific compatibility code out of the kernel path if possible.
- Preserve the genericity rule already enforced by `tools/aether2_genericity_check.py`.

### `runner/` legacy surfaces

`runner/README.md` already treats a lot of the top-level `runner/` files as historical. That matches the code layout.

Recommended treatment:

- keep `runner/aether2/` public;
- move `runner/active_evidence_kernel.py`, `runner/kernel_*.py`, `runner/packet0*.py`, `runner/successor_*.py`, and other historical slices into an archive namespace;
- keep only the thin public compatibility shims that are truly needed.

This tree is currently mixed enough that `runner/` as a whole is `needs decision` even though its `aether2` child is publication-ready.

### `tools/`

This is a real operational surface, not just helper scripts.

Strong public items:

- `tools/aether2_genericity_check.py`
- `tools/aether2_decision_trace.py`
- `tools/aether2_fake_progress_homologs.py`
- `tools/aether2_grader_isolation.py`
- `tools/aether2_targeted_board.py`
- `tools/render_final_harness_scoreboard.py`
- `tools/run_aether2_fake_progress_runner.py`
- `tools/run_aether2_g2.py`
- `tools/run_aether2_g3_official.py`
- `tools/run_final_harness_eval_suite_baseline.py`

Publication risk:

- `tools/run_aether2_tournament.sh` currently hardcodes a eval-specific task root default: `/home/azureuser/terminal-workflow-official/original-tasks`.
- Any launcher that bakes in eval naming or private filesystem paths should be split into a generic public launcher plus private eval wiring.

### `tests/`

This is one of the strongest public surfaces in the repo.

It already covers:

- `runner/aether2` modules;
- certified sandbox contracts;
- eval substrate contracts and scoreboard logic;
- tool-call composite/terminal-workflow adapters;
- genericity checks;
- model-client wrappers;
- lifecycle and launch scripts;
- contamination and grader isolation checks.

This should absolutely be part of the public release, but only after caches and generated artifacts are removed.

### `evals/`

This should remain public, but it needs cleaning and expansion into the real eval substrate.

The current files are intentionally narrow:

- `evals/context_eval.py`
- `evals/step_efficiency_eval.py`
- `evals/verification_eval.py`

This is acceptable as a public starter surface, but the repo still needs a richer public eval package with:

- task packs;
- fixtures;
- verifiers;
- graders;
- result rows;
- contamination labels;
- sentinels;
- family-level boards;
- clean custom/homolog packaging.

### `experiments/`

This is currently a lightweight public experiments shell:

- `experiments/configs/example.yaml`
- `experiments/results/scoreboard.md`
- `experiments/runs/` is already gitignored

This is good public shape, but the scoreboard is still a placeholder and needs real evidence-backed content.

### `tracking/collab/`

This is the biggest publication risk and the biggest curation opportunity.

What can be salvaged for public use:

- `tracking/collab/skills/analyze-agent-runs/` as a public skill package, after sanitization;
- selected synthesis docs, case studies, and dossiers, once exported into `docs/`;
- variant hypotheses and cleaned eval-board summaries, once moved out of raw collaboration folders.

What should not ship as-is:

- `runs/`;
- `vm_pulled_runs/`;
- `workspace/`, `host_workspace/`, `workspace_fixture/`;
- `*.tar.gz`, `*.zip`, `*.log`, `*.jsonl` raw run payloads;
- raw review transcripts and receipt ledgers;
- pressure-family evidence bundles that expose hidden truth or private task structure.

The public version of this tree should be split into exported docs only:

- curated docs and case studies;
- a small public eval board;
- sanitized skill packages;
- a private raw-history store that is excluded from the public repo.

### `tracking/ledger/`

This should not be published verbatim.

The ledger is valuable, but the current structure is too revealing for a public repo:

- canonical historian files;
- raw inbox handoffs;
- operational failure detail;
- open questions and decision history.

Best public pattern:

- keep the canonical ledger private;
- publish a redacted `docs/history/` or `docs/public-ledger/` view;
- keep only milestone summaries, selected decision rationales, and links to public evidence.

### `research/`

This is useful, but it is mixed between curated research and raw source corpus.

Good public candidates:

- `research/analysis/` curated synthesis notes;
- `research/notes/` if redacted and organized;
- `research/source_finder_prompt_pack/` as a reusable sourcing workflow;
- `research/source_intake_checklist.md` if sanitized for public use.

Keep private or heavily gate:

- `research/sources/` raw trajectories, mirrored codebases, `.tar.gz`/`.zip` source bundles, and source dumps;
- `research/intake/` raw intake, rejected sources, and staging;
- `research/external/` mirrored external repositories unless every source is license-cleared;
- raw trace or corpus extracts under `research/analysis/*/output/` if they expose too much provenance or private data.

### `blocks/`

This is a public core candidate.

It should remain a clean, testable library of harness dimensions and variants.

### `variants/`

You want the variant code included, and that is the right call.

Recommended public content:

- source code for each variant family;
- explicit config files;
- variant README files;
- scoreboards and hypothesis notes;
- local sentinels and regression tests.

Do not publish:

- raw run directories;
- VM copies;
- `.pytest_cache/`;
- temporary workspaces;
- generated artifacts and logs.

The key change is that variants are code packages, not evidence dumpsters.

### `prompts/`

This should be public, but rewritten with a public-facing boundary.

Good public structure:

- base prompts;
- variant prompts;
- specialist prompts;
- small guidance docs.

Avoid shipping internal/private operator instructions in the same folder unless they are clearly marked as non-public.

### `website/`

This should become the public front door.

Current status:

- it is still mostly default Next.js scaffolding;
- it has `node_modules/` and `.next/` build output locally;
- it contains `AGENTS.md` and `CLAUDE.md`, which are likely internal workflow helpers.

Recommended public stance:

- publish the site code;
- exclude build output and dependency trees;
- move or sanitize internal agent docs if they are not meant for visitors.

### `scripts/`

This is a good public operational surface.

It currently contains:

- VM lifecycle helpers;
- deployment helpers;
- deallocation/autoshutdown scripts;
- tournament launch scripts;
- runtime bundle builders.

These are useful, but any script with eval-specific defaults should be split into:

- generic public wiring;
- private eval adapters;
- environment-specific defaults via config or env vars, not hardcoded paths.

## Dangerous or Noisy Items for Public Release

These are the clearest "do not publish as-is" classes:

1. Raw trajectories, logs, receipts, and run payloads under `tracking/collab/**/runs/`, `vm_pulled_runs/`, `workspace/`, `host_workspace/`, and `workspace_fixture/`.
2. Vendored environments and caches: `.venv/`, `venv/`, `website/node_modules/`, `website/.next/`, `__pycache__/`, `.pytest_cache/`.
3. Generated bundles and exports: `repomix-output.xml`.
4. Mac metadata: `*.DS_Store`.
5. Archived artifacts and source bundles: `*.tar.gz`, `*.zip`, `*.jsonl`, `*.log`, `*.db`, `*.sqlite*` where they expose raw evidence.
6. Eval corpora and private task data under `official_tasks/`, `tasks/`, `research/sources/`, and parts of `tracking/collab/final_harness_eval_suite/`.
7. Private-ledger material under `tracking/ledger/`.
8. Eval-specific launcher defaults and hardcoded private paths in helper scripts.

## Proposed Public Repository Structure

This is the structure I would aim for after cleanup.

```text
/
  README.md
  AGENTS.md
  pyproject.toml
  .gitignore
  src/
    aether2/
  blocks/
  evals/
    custom/
    homologs/
    families/
    sentinels/
    boards/
  experiments/
    configs/
    results/
  prompts/
  scripts/
  variants/
    <family>/
      <variant>/
        src/
        config.yaml
        README.md
        scoreboard.md
        sentinels/
  skills/
    analyze-agent-runs/
    loop-orchestrator/
    runner-ops/
  tests/
  tools/
  website/
  docs/
    architecture/
    case-studies/
    research-notes/
    history/
    release-notes/
  variants/
    <family>/
      <variant>/
  archive/
    legacy-runner/
    legacy-docs/
```

Practical mapping from the current tree:

- `runner/aether2/` -> `src/aether2/`
- `tracking/collab/skills/analyze-agent-runs/` -> `skills/analyze-agent-runs/`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/` -> `docs/case-studies/`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/` -> `docs/research-notes/source-system-dossiers/`
- `tracking/collab/final_harness_eval_suite/` curated summaries -> `evals/custom/`, `evals/families/`, or `docs/eval-board/`
- `tracking/variants/` curated variant families and code -> `variants/`
- `tracking/ledger/` curated summaries -> `docs/history/`

## Migration Plan

### Phase 1: Minimal hiring-ready public surface

Goal: ship the smallest credible open-source repo that a strong engineer can understand quickly.

Keep:

- `README.md`
- `src/aether2/` or `runner/aether2/`
- `tests/`
- `evals/`
- `blocks/`
- `scripts/`
- `tools/`
- `variants/`
- `website/`
- a curated `docs/` set

Exclude:

- raw run histories;
- private ledgers;
- caches and environments;
- eval corpora;
- source dumps and tarballs.

### Phase 2: Deeper production cleanup

Goal: make the public tree feel like a maintained product, not a lab dump.

Do this next:

- split current/legacy runner code cleanly;
- formalize `docs/architecture/`;
- formalize `docs/case-studies/`;
- curate `docs/history/`;
- package `variants/` by family with code, scoreboards, and rationales;
- turn `evals/` into a real task-pack/verifier/grader substrate for custom and family-level evals;
- remove eval-specific paths from generic scripts.

### Phase 3: Optional website/docs polish

Goal: make the repository easy to browse and easy to trust.

Add:

- polished landing page;
- architecture diagrams;
- eval board summaries;
- curated case studies;
- release notes;
- contribution guide;
- a public/private data boundary page.

## What To Do With Specific Surfaces

### Research / deep synthesis outputs

Publish as curated notes, not as a raw archive.

Recommended public packaging:

- `docs/research-notes/`
- `docs/case-studies/`
- `docs/research-notes/source-system-dossiers/`
- `docs/research-notes/eval-dossiers/`

Do not publish:

- raw source dumps;
- unfiltered intake;
- rejected sources;
- dense trace exports without redaction.

### Variants

Keep them, but make them legible.

Recommended public packaging:

- one folder per family;
- one folder per variant;
- variant source code and configs;
- `variant.md` or `README.md` with hypothesis, score delta, and sentinels;
- `scoreboard.md`;
- `rationale.md`;
- `config.yaml`.

Do not publish:

- raw run directories;
- VM copies;
- generated workspaces;
- trace caches;
- checkpoint noise.

### Ledger

Do not publish the canonical ledger verbatim.

Best public compromise:

- a redacted public history;
- milestone and decision summaries only;
- links to public evidence;
- no raw inbox entries;
- no operational noise;
- no private negative examples unless they are sanitized into case studies.

### Custom evals / homologs

Publish the good ones, not the contaminated ones.

Recommended public packaging:

- `evals/custom/` for original tasks;
- `evals/homologs/` for pressure-family abstractions;
- `evals/families/` for grouped family-level evals;
- each eval with task pack, fixture, verifier, grader, baseline, ceiling check, and sentinels.

Keep private:

- direct eval clones;
- any `official_tasks/` source tree;
- rows with licensing ambiguity;
- hidden-truth payloads that would expose private eval content.

### Skills

Publish the useful ones and make them modular.

Recommended public packaging:

- `skills/analyze-agent-runs/`
- `skills/loop-orchestrator/`
- `skills/runner-ops/`

Each skill should have:

- `SKILL.md`
- `references/`
- `scripts/`
- `agents/` only when genuinely needed

### `AGENTS.md` / `CLAUDE.md` / `CODEX.md`

Use them, but keep them public-safe.

Recommended policy:

- root `AGENTS.md` should become a short contributor and repository-operating guide;
- detailed internal governance should move to private or non-public docs;
- per-subtree agent docs should exist only where they add clear public value;
- if `CLAUDE.md` or `CODEX.md` exists only for internal workflow, do not ship it verbatim.

## README / Architecture / Case Studies Outline

### `README.md`

- what this repo is;
- what it is not;
- quick start;
- repo map;
- public/private boundary;
- core architecture summary;
- eval philosophy;
- how to run tests;
- how to read scoreboards and case studies.

### `docs/architecture/overview.md`

- system layers;
- data flow;
- sandbox contract;
- verifier/grader boundary;
- trace and receipt capture;
- memory and compaction;
- recovery and monitoring;
- security and public/private boundaries.

### `docs/case-studies/`

For each case study:

- problem;
- failure pressure;
- evidence used;
- what changed;
- why it mattered;
- evaluation result;
- regression sentinels;
- remaining risk.

Recommended first case studies:

- tool-contract reliability;
- verification/completion correctness;
- long-horizon recovery;
- context compaction under pressure;
- eval-native sandbox contract.

## Risk List

1. Publishing raw trajectories or logs would leak too much operational detail.
2. Publishing `official_tasks/` or `tasks/` would directly violate the chosen public boundary.
3. The current ledger structure is too revealing to ship verbatim.
4. `research/sources/` contains raw corpora and source mirrors that should not be treated as public docs.
5. The repo currently contains a lot of cache and environment noise that will make the public tree look immature.
6. Some helper scripts still assume eval-private paths and should be split or parameterized.
7. The website is not yet a polished public front door.
8. `runner/` is mixed current-plus-legacy and should be flattened before publication.

## Open Questions

1. Which pressure-family assets are worth keeping only as private local references versus re-expressing as custom evals?
2. Should the canonical ledger remain in a private side repo, with only a curated public history here?
3. Which current `tracking/collab/` artifacts deserve promotion into public `docs/` versus permanent archival?
4. Is `runner/aether2/` the final public module root, or should the project move to a `src/` layout before release?
5. Do we want public `CLAUDE.md` / `CODEX.md` files at all, or only one sanitized `AGENTS.md`?
6. Should `website/` be a marketing/docs site only, or also a browsable eval board and case-study portal?

## Evidence Paths Inspected

Representative paths read during this inventory:

- `README.md`
- `pyproject.toml`
- `runner/README.md`
- `runner/aether2/__init__.py`
- `runner/aether2/loop.py`
- `runner/aether2/prompts.py`
- `runner/aether2/tools.py`
- `tools/aether2_genericity_check.py`
- `scripts/run_aether2_tournament.sh`
- `tests/test_certified_sandbox_contract.py`
- `tests/test_eval_substrate_contracts.py`
- `tests/test_aether2_genericity.py`
- `evals/context_eval.py`
- `experiments/README.md`
- `tracking/collab/README.md`
- `tracking/ledger/README.md`
- `tracking/collab/stage_02_synthesis/README.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/README.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/README.md`
- `tracking/collab/final_harness_eval_suite/task.md`
- `tracking/collab/final_harness_eval_suite/pressure_family_provenance.yaml`
- `tracking/collab/final_harness_eval_suite/final_suite_registry.yaml`
- `research/README.md`
- `research/source_intake_checklist.md`
- `website/README.md`
- `website/package.json`
- `.gitignore`

## Bottom Line

The repo is close to being a strong public research-product portfolio, but only if it is published as a curated artifact set rather than as a raw workspace snapshot.

The biggest wins are:

- keep the harness core;
- keep the tests and eval substrate;
- publish curated research and case studies;
- include variant code, not variant traces;
- hide raw history, raw corpora, and environment noise.
