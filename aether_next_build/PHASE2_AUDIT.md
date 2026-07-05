# Aether-Next — Phase 2 Audit (Terminal-Bench 2.0, 10 tasks × 2 models)

Date: 2026-06-27. Runner: docker-exec pilot on VM (azureuser@20.106.35.151).
Solvers: **gpt-5.4-mini** and **gpt-5.3-codex** (both also as architect).
Effort: medium. Max steps: 30. Reward = official `test.sh` -> `/logs/verifier/reward.txt`.

## Headline

| Model | Real reward | Clean full attempts | config_invalid | runner crashes |
|-------|------------|---------------------|----------------|----------------|
| gpt-5.4-mini  | **3 / 10** | 10 / 10 | 0 | 0 |
| gpt-5.3-codex | **3 / 10** | 10 / 10 | 0 | 0 |

Both harness fixes shipped this session are **proven across 20 runs**:
- **Architect-IR fallback** (kernel degrades a fatally-invalid architect config to a
  guaranteed-valid default instead of aborting) -> **0 config_invalid** (was aborting
  openssl/fix-git before the solver ran).
- **Subprocess decode hardening** (`errors="replace"` on all text-mode `subprocess.run`)
  -> **0 crashes**; train-fasttext went from `error/UnicodeDecodeError` to a clean attempt.

## Per-task results

reward | status | steps | reconfigs | classifier

| task | MINI | CODEX |
|------|------|-------|
| openssl-selfsigned-cert | 1.0 comp st3 rc0 none ✓ | 1.0 comp st24 rc0 none ✓ |
| log-summary-date-ranges | 0.0 comp st13 rc0 none | **1.0** inco st30 rc0 model_limit ✓ |
| fix-git | 0.0 inco st30 rc1 harness_context | 0.0 inco st30 rc0 harness_context |
| filter-js-from-html | 0.0 comp st15 rc0 none | 0.0 comp st2 rc0 none |
| gcode-to-text | 0.0 inco st30 rc0 model_limit | 0.0 inco st30 rc0 harness_context |
| extract-elf | **1.0** inco st30 rc1 substrate_missing ✓ | 0.0 inco st30 rc0 substrate_missing |
| raman-fitting | 0.0 inco st30 rc0 harness_context | 0.0 inco st30 rc0 harness_context |
| sparql-university | 0.0 comp st22 rc1 none | 0.0 inco st30 rc0 substrate_missing |
| constraints-scheduling | 1.0 comp st2 rc0 none ✓ | 1.0 comp st1 rc0 none ✓ |
| train-fasttext | 0.0 inco st30 rc2 model_limit | 0.0 inco st30 rc0 harness_context |

## Limiter attribution (harness vs model) — evidence-backed

### Genuine HARNESS limiter (blocks a capable model from even attempting)
- **fix-git (BOTH models)** — HIGH confidence, fixable. *Every* git command returns
  `exit=128` while `find`/`ls` succeed. exit 128 is git's own fatal refusal — the classic
  **"dubious ownership"** error from a workspace owner / exec-user mismatch inside the
  container. The model tried 7+ distinct git invocations; all were walled off by the
  container setup. Reproducible across mini AND codex -> not a model weakness.
- **gcode-to-text (codex; partial)** — a 1.66 MB input file. After `read_file` +
  `artifact_inspection` (truncated to 100 K chars), only 4 receipts in 30 steps: the
  solver loop stopped surfacing real turns. Large-input context flooding is a harness
  context-management limit.

### HARNESS measurement bugs (the run is fine; the harness mislabels it)
- **Completion-gate false-negatives**: `reward=1.0` but `status=incomplete`.
  - CODEX log-summary: solved (grader 1.0) yet gate said incomplete -> "model_limit".
  - MINI extract-elf: solved (grader 1.0) yet gate said incomplete -> "substrate_missing".
  The internal completion gate is stricter than / misaligned with the authoritative
  checks and under-credits genuine successes. A reward=1.0 must never be `incomplete`.
- **Classifier over-attribution to substrate**: extract-elf / sparql 127-errors come from
  the *model* using tools absent in a minimal image (`file`, `python` (only `python3`
  exists), `rg`, `rdflib`) and not adapting / not bootstrapping. These are
  model-adaptation failures, but the classifier tagged them `substrate_missing`
  (harness-ward). raman-fitting similarly: model never `pip install`ed numpy/scipy.

### MODEL limiter (harness gave a clean runtime; model produced wrong/no solution)
- log-summary (mini), filter-js (both), sparql (mini), train-fasttext, extract-elf (codex),
  raman (both): wrong answer accepted by gate but rejected by grader, or no convergence in
  30 steps. These are legitimate capability misses.

## Recommendations (in priority order)

1. **Fix the git ownership wall (fix-git).** In the container bootstrap, run
   `git config --global --add safe.directory '*'` (or chown the seeded workspace to the
   exec user / `docker exec -u`). This converts fix-git from a harness-blocked zero into a
   real model-capability test. Single highest-value fix; affects every git task.
2. **Align the completion gate with authoritative checks.** Investigate why the gate
   reports `incomplete` when the grader passes (codex log-summary, mini extract-elf).
   reward=1.0 with status=incomplete is a contradiction the gate must not produce.
3. **Refine the classifier's substrate vs model boundary.** Distinguish "substrate
   genuinely absent and unobtainable" from "model used a missing tool / didn't bootstrap
   deps it could have installed." The 127-on-`file`/`python` and missing-numpy cases are
   model-adaptation failures, not harness limits.
4. **Large-input handling (gcode).** A 1.66 MB file degrades the solver loop even with
   100 K-char truncation. Add size-aware/chunked file strategies so big inputs don't
   starve the loop.
5. **Convergence tuning.** Most misses hit st30 (max-steps) without converging and with
   few reconfigures. Consider a higher step budget and/or a sharper reconfigure trigger.

## Bottom line

The harness is now **structurally sound**: 20/20 clean full attempts, zero aborts, zero
crashes — the two limiter classes fixed this session (config_invalid, decode crash) are
gone. Remaining gap to a *fair* benchmark is small and well-localized: **one real harness
bug (git ownership)** plus **two measurement bugs** (completion-gate false-negatives,
classifier substrate over-attribution). Raw capability on this slice is 3/10 for both
gpt-5.4-mini and gpt-5.3-codex; codex shows a slightly stronger profile (it genuinely
solved log-summary, which mini missed) masked by a gate false-negative.
