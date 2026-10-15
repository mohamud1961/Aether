# J1: can a per-requirement judge tell right finishes from wrong ones? (pre-registered 15 October 2026)

## Why

The principal's proposal: keep the requirement ledger and let a Reviewer-like checkpoint judge each requirement and decide.
Before building any of it, measure whether a judge has signal on graded trajectories we already hold. If no judge
separates right from wrong finishes here, no checkpoint design built on it can.

## Design

- **Inputs** (`tools/aether_program/core_judge_inputs.py`; file sha256 `05519e0573f761bd2954983211549a0bd67e31fd9b7eff1d361a6e4d7a8fa4a3`): 110 graded finishes.
  - **G4 Codex + GPT-6-Astra**: all trials of the 17 tasks where GPT-6-Astra both passes and fails (80 trials kept;
    5 dropped for having no plain-text task message). Same task, same agent, different outcomes: the hard case.
  - **N2 Aether + GPT-6-Luna**: all 30 rows.
  Each holds the task, its requirement sentences (`ledger.sentences`) and the work record (commands, outputs
  clipped to 1,200 chars, the record to its last 40k chars, the final message). Rewards are kept for scoring only.
- **Judge**: GPT-6-Luna (Responses API), one call per input, `tools/aether_program/core_judge_bench.py`: per
  requirement met / not_met / unclear "from the task's own words and the outputs shown, not the agent's claims",
  and p_pass 0–100. On G4 the judge is a different model from the agent; on N2 it is the same model (shared prior).
  GLM and SubQ Snap / Reviewer are not included: no key on the run host / no access (recorded, not substituted).

## Predictions (before any judge call)

- **J1-a (signal, different model):** on G4 GPT-6-Astra, AUROC of p_pass ≥ 0.70 (base: chance 0.5).
- **J1-b (gate):** on G4 GPT-6-Astra, admitting only finishes with no not_met raises precision from the base (43/80 =
  54%) to ≥ 70% while keeping ≥ 70% of passes.
- **J1-c (same model):** on N2, AUROC ≥ 0.65 (expected weaker: the judge shares the solver's readings).
Honest prior: uncertain; the R1 reviewer (GLM, state access) caught 3/12. A null result is recorded as null.

## Budget

≈ 1.0M input tokens; estimate ≈ $0.15–0.40 at GPT-6-Luna prices. Kill at $1.00 recorded. Authorized by the principal ("go",
15 Oct, on the judge test).

## Amendment before any judge call (15 Oct, 15:2x UTC): judge context and evidence-first prompt

The principal asked that the judge get the context it needs to judge correctly. Changed before any judge call:
- **Delivered files (G4 only):** each trial's collected artifacts (the task's artifact manifest) as a tree with sizes
  plus the text of small text files (≤ 4,000 chars each, ≤ 20,000 in all). `logs/` and `shared/` are never shown
  (harness logs; possibly grader-side). Grader output is not under artifacts. Leak scan of all 110 records: the only
  hits for test/grader words are the agents' own workspace files and math-eval-grader's own task. N2 rows have no
  saved artifacts (recorded limit).
- **Fuller recent outputs:** the last 12 outputs kept to 4,000 chars (others 1,200); record cap 80k chars (was 40k).
- **Evidence-first judge (Sauron, arXiv 2610.17724):** each verdict must quote the output or file that settles it;
  the agent's statements are claims, not evidence; met only on shown evidence.
- Inputs file sha256 `396f6bc1db0433e5a566e703d2a5ad21681643756bb2e14c6ee82c65b855e93b` (110 rows, same trials, ≈ 6.6M chars). Budget estimate ≈ $0.3–0.5; kill $1 unchanged.
Predictions J1-a/b/c unchanged. **Exploratory (not a prediction):** for each wrong finish the judge admits, I will
classify the miss as *unsupported claim* or *reading* from the judge's quoted evidence and the grader's failing test.

## Cache-key smoke (15 Oct, 14:55 UTC, `48f5abaaf`, not part of J1)

One binary-extract row, arm `e`, GPT-6-Luna: request accepted with `prompt_cache_key` (0 failed attempts), 8 calls, cache
77.9% of 64.8k input (N1 `e` on the same task: 76.8–78.2% at 9–10 calls), $0.005, reward 0. The key is accepted
and harmless; no change in cache hit is measurable on a run this short (the prefix was already cached).
