# Continuation State - 2026-06-16

Status: public-readiness continuation checkpoint.

## Current Committed Public Slices

- `5389a6550` - Strengthen workflows agentic engineering showcase.
- `a9567e1d5` - Reorganize public eval and variant proof surfaces.
- `35320de9a` - Add public docs and curated research surfaces.
- `5a7444308` - Remove moved research methodology source files.

## Latest Cleanup Intent

The public repo should remain easy to continue and should not publish raw
trajectories, mirrored codebases, official benchmark tasks, hidden graders, or
answer keys.

The public-facing eval references were sanitized so they describe calibration
pressure without copying private task logs or official-task language:

- `eval_suite/calibration_lanes/terminal/reference/final_harness_task.md`
- `eval_suite/whole_harness/final_harness_v1/task.md`

The provenance docs were softened so they do not present local quarantined
source paths as public repo artifacts:

- `docs/provenance/agent_runtime_adaptation_policy.md`
- `docs/provenance/third_party_notices.md`

## Required Next Git Action

The repository already has ignore rules for raw/private sources:

- `research/sources/`
- `research/intake/`
- `official_tasks/`

However, many files under `research/sources/` and `research/intake/` are
already tracked from earlier history. They should be removed from the Git index
while preserving the local files on disk:

```bash
git rm -r --cached --ignore-unmatch research/sources research/intake official_tasks
git commit -m "Stop tracking raw research source assets"
```

In this Codex sandbox, `git rm --cached` repeatedly failed with:

```text
fatal: Unable to create '.git/index.lock': Operation not permitted
```

No stale `.git/index.lock` file was present. Run the command above from a normal
local terminal if Codex cannot acquire the index lock.

## Continue-Project Notes

The next agent should:

1. Keep `workflows/`, `eval_suite/`, `variants/`, `docs/`, and curated
   `research/` as the public proof surface.
2. Keep raw trajectories, mirrored codebases, benchmark captures, and official
   task assets local/private.
3. Prefer public-safe derived summaries over raw source publication.
4. Preserve the latest committed eval/variant/workflow structure.
5. Before publication, run:

```bash
git ls-files 'research/sources/**' 'research/intake/**' 'official_tasks/**'
rg -n "<private-repair-log phrases>" docs eval_suite variants workflows research/case_studies research/methodology research/phases research/synthesis
git status --short
```
