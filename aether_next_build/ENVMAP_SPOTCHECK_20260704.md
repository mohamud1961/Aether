# EnvMap Spot Check

Date: 2026-07-04

Purpose:
- Validate whether the deterministic EnvMap audit is only trustworthy in the aggregate,
  or whether selected row-level judgments are also accurate enough to use in planning.
- Spot-check one task from each requested bucket:
  - sparse task
  - prompt-output mismatch task
  - heavy visible test task
  - apparently clean task

Scope:
- Deterministic only.
- No model calls.
- No Docker.
- No verifier/grader.
- Ground truth is the live checkout under `official_tasks/` plus the live
  `build_envmap_from_task()` output.

## Tasks Checked

### 1. Sparse task: `adaptive-rejection-sampler`

Audit row:
- `visible_file_count=2`
- `top_level=["Dockerfile", "protected.tar.gz.enc"]`
- flags:
  - `sparse_visible_workspace`
  - `deliverable_pressure_with_few_input_hints`

Live workspace check:
- `official_tasks/adaptive-rejection-sampler/environment/` contains only:
  - `Dockerfile`
  - `protected.tar.gz.enc`
- Instruction requires new deliverables:
  - `/app/ars.R`
  - `/app/normal_samples.txt`
  - `/app/exponential_samples.txt`

Judgment:
- Mechanically correct.
- Semantically correct.

Notes:
- This is a genuinely sparse surface.
- The board is not exaggerating here; the task really exposes almost no visible
  implementation material in the environment workspace.

### 2. Prompt-output mismatch task: `constraints-scheduling`

Audit row:
- visible inputs found under `inputs/`
- `prompt_declared_output_missing_paths=["meeting_scheduled.ics"]`
- flag:
  - `prompt_declared_output_not_visible`

Live workspace check:
- Visible inputs:
  - `inputs/alice_calendar.ics`
  - `inputs/bob_calendar.ics`
  - `inputs/carol_calendar.ics`
- Output required by the prompt:
  - `/app/meeting_scheduled.ics`
- That output file is not present in the initial workspace.

Judgment:
- Mechanically correct.
- Semantically true, but easy to misread.

Interpretation refinement:
- The flag does **not** mean EnvMap failed to surface an existing file.
- It means the prompt names a required output path that is not already present
  in the visible workspace.
- For deliverable-generation tasks, that condition is often expected.

Recommendation:
- Keep the flag, but treat it as a planning signal rather than a likely harness
  defect.
- Better mental label: `declared_output_not_preseeded_in_workspace`.

### 3. Heavy visible test task: `schemelike-metacircular-eval`

Audit row:
- `visible_file_count=67`
- `likely_tests_or_checkers_count=25`
- flag:
  - `heavy_visible_test_surface`

Live workspace check:
- Environment workspace contains:
  - `tests/interp.py`
  - `tests/test_outputs.py`
  - large `tests/test/` tree
  - large `tests/shadow_test/` tree
- The visible test/check surface is genuinely much larger than typical tasks.

Judgment:
- Mechanically correct.
- Semantically correct.

Notes:
- This row is a strong example of the board being useful beyond simple counts:
  it identifies a real reduction/selection pressure task where the solver and
  verifier need disciplined evidence handling.

### 4. Apparently clean task: `fix-git`

Audit row:
- no risk flags
- visible workspace includes:
  - `Dockerfile`
  - `resources/patch_files/...`
  - `setup.sh`

Live workspace check:
- The environment is small but not empty.
- The instruction is brief and does not declare many explicit output paths.
- The visible workspace contains plausible concrete task material.

Judgment:
- Mechanically correct.
- Semantically mostly correct.

Notes:
- "No flags" here does not mean "easy" or "fully understood".
- It means the row does not trigger the current structural risk heuristics.
- This is an example of a row that looks appropriately unalarming, not a proof
  that the task is trivial.

## Overall Assessment

My honest row-level conclusion after spot checking:

- Mechanically: the checked rows are accurate.
- Semantically: the rows are useful, but some flags need careful reading.

What held up well:
- sparse workspace detection
- heavy visible test/check surface detection
- visible input path detection

What needs interpretation discipline:
- `prompt_declared_output_not_visible`

That flag is real, but it should not automatically be treated as evidence of a
harness surfacing defect. In many tasks it simply means the deliverable has to
be created during the run.

## Result

The board appears trustworthy enough for planning at the row level, with one
important caveat:

- Trust the aggregate findings strongly.
- Trust the row mechanics substantially.
- Do not treat every risk flag as the same kind of problem.
- In particular, read `prompt_declared_output_not_visible` as a task-shape
  signal unless separate evidence shows a genuine surfacing miss.
