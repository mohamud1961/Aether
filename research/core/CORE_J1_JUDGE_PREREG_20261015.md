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
