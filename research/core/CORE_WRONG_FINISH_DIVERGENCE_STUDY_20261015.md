# Wrong finishes across agents: what recurs, and how the passing runs differed (15 October 2026)

Asked for by the principal ("is this a recurring theme, if not how did they solve it; build on the shoulders of giants")
and by ChatGPT's review (find the first meaningful divergence, classify, then one minimal intervention against the
dominant type). Offline study of traces already in custody; no model calls.

## Sources

Local per-row archives (graded by the official grader): B1 (Aether-Core, GLM), S4, S5, S6 (Aether-Core, GLM arms),
T1 (Terminus-2, GLM), L1, L2 (Aether-Core, GPT-6-Luna), N1 A3 (Aether-Core, GPT-6-Luna). 100 passing rows and 60 failing rows on
the nine-task development board. Script: the per-row table was produced from `verifier/reward.txt`,
`verifier/test-stdout.txt` and the agent traces. These are **development tasks**: nothing here touches the held-out
list (`CORE_N1_HELDOUT_20261015.json`).

## 1. Failures recur by task, across harnesses and models

Wrong voluntary finishes (reward 0 after the agent called finish), grouped by the grader's assertion:

| Task | Wrong finishes | Grader assertion (recurring) | Who fails / who passes |
|---|---|---|---|
| construct-assembly | 12 | component sequence not found in the order flag-donor-dhfr-acceptor-snap | all harnesses and models fail; 2 GLM passes (S5 x2 e1, S6 x2r e2) |
| net-fit | 12 | learned DAG edges reversed / extra | GLM (Aether and Terminus) mostly fails; GPT-6-Luna 4/4 pass; Terminus 1/2 |
| seq-assembly | 9 | a stated primer constraint violated (Tm gap, clamp, BsaI site, non-ACGT) | almost all fail; 2 GPT-6-Luna passes (L1 e2, L2 e2) |
| binary-extract | 6 + 1 | 0% of expected values (invented 0x400000 base); 1 GLM row signed-integer values | GPT-6-Luna 0/6; GLM Terminus 2/2, GLM Aether mostly pass |
| graph-query-catalog | 5 | one professor missing (has an EU department) | mixed; most rows pass |
| credential-recovery-recovery | 1 | truncated answer | — |

So the failures are not one model's quirk. Each task has its own trap that recurs across agents, and the two models
have **different** blind spots (GPT-6-Luna passes net-fit where GLM fails; GLM passes binary-extract where GPT-6-Luna fails). Neither
is simply too weak: both can do each task, and which reading they settle on varies.

## 2. First divergence, read in depth (4 cases)

- **binary-extract, GPT-6-Luna L2 e1 (fail).** In its first Python cell it compared the example's value at 4194304 with the
  file's first word under the 0x400000 mapping and saw they differ (0x6a617e69 vs the binary-extract magic). It later dismissed
  the example values as "random binary values", kept the example's base, and validated its output against its own
  mapping. Most of its turns carry no written reasoning (forced tool calls). **Divergence: an observed refutation of
  the reading was explained away.** L1 (same model, JSON turn with a written analysis every turn) wrote "the example's
  first address 0x400000 suggests a fixed load base" and failed the same way, so per-turn written analysis alone does
  not separate pass from fail.
- **binary-extract, Terminus GLM e1 (pass).** Wrote: "for a conventional non-PIE binary this naturally produces
  addresses beginning at 0x400000, as in the example" — the example read as a format illustration — and used the
  file's virtual addresses; then reasoned about the grading rule (wrong keys fail) to drop risky entries.
- **construct-assembly, GPT-6-Luna (fail) vs GLM S5 x2 e1 (pass).** The task says the donor/acceptor sequences "should match
  the fasta file returned by the pdb API". The failing run removed the PDB entry's N-terminal tag and replaced the
  FASTA's X with a single Ala (its own domain judgement, recorded as a decision). The passing run wrote "use exactly
  the PDB FASTA sequence … minus the N-terminal M", and worked out that X is the GFP chromophore (three residues
  condensed into one chemical component), expanding it rather than substituting.
- **seq-assembly, GPT-6-Luna L2 e1 (fail).** Claimed every primer pair within the 5 °C limit using `oligotm`; the grader
  measured 5.86 °C. The task defines Tm "with respect to only the part of the primers that anneal to its respective
  template" with exact oligotm flags; the run's check used its own notion of the annealing part, so it could not fail.

## 3. Classification (dominant type)

Across 5 of the 6 recurring tasks the delivered output violates a requirement **stated explicitly in the task
text** (the FASTA must match; the alphabetical tie rule and `to,from` order; the Tm definition and flags; the
criteria list), and the run's own checks tested **its operationalisation** of that requirement, not the text. The
remaining type (binary-extract) is an example read as data, with an observed contradiction explained away. In every
deep-read failure the decisive point was **noticed** (a mismatch computed, an X discussed, a tag recognised) and then
settled by the model's own judgement without a check that could have gone the other way.

Limits: classes for the 60 rows come from the grader's assertion, not from reading each trace; 4 rows were read in
depth. Whether each failing run noticed its decisive point is shown only for those 4.

## 4. Prior art (what other agents do)

- **Terminus-2** (the strongest baseline we have): a written analysis and plan every turn, no requirement list. It
  fails construct-assembly, seq-assembly and net-fit the same way, so its format is not the fix for the dominant type, and L1 shows the
  written-analysis format did not fix binary-extract for GPT-6-Luna.
- **Claude Code (TodoWrite) and Codex CLI (update_plan)**: the agent keeps an explicit, updated list of what the task
  requires and marks items done as it works. This is established practice in the strongest coding agents and is the
  nearest prior art to a requirement tracker. Neither ties items to the task's own wording or checks coverage.
- **Aether already tried, on GLM** (S1–S6, L1/L2): finish-time self-check paragraphs, an analysis turn, a JSON turn,
  receipts, reasoning effort, and a contradiction rule in the prompts. None cut wrong finishes. Rules stated in the
  prompt ("a contradiction is never explained away"; "an example that cannot be reproduced shows the format only")
  were present and broken. Prompt text is exhausted as a lever.

## 5. Proposed minimal intervention (not built; for review)

**A requirement ledger kept during the work, bound to the task's own words**, built on the TodoWrite/update_plan
pattern:

- Each item **quotes the task verbatim** (the harness checks the quote is a substring of the task text: mechanical),
  states how the run reads it, any other reading it can see, and the step(s) whose result shows it met.
- **Coverage is mechanical**: every requirement sentence/bullet of the task text must be quoted by some item before
  finish; uncovered sentences are shown to the solver at its first finish (the net-fit tie rule, the FASTA-match
  bullet and the Tm definition would each have had to be addressed by name).
- Evidence mode's citation-shape check applies to the cited steps (exists, not failed, not stale).

What it cannot do: it does not know whether a reading is right, and a cited step is not semantic proof (Codex: a
tracker records model beliefs). Its bet is narrower: the dominant failures sit on requirements that are stated in the
text, and forcing each stated requirement to be quoted, read and shown — while working, not at finish — moves
attention onto exactly those sentences.

**Order change (from the overnight plan):** this replaces snapshot/rollback as the next build, because the evidence
points at reading, not at undo. Snapshots stay on the list.

**Measurement (needs user authorization, sealed cost):** paired, same model and resources, on the development tasks
with recurring failures (construct-assembly, seq-assembly, net-fit, binary-extract, graph-query-catalog), ledger on vs off, ≥ 2 episodes; outcomes graded
by the official grader only after the run; metrics per Amendment 4 (all-scheduled success, asserted-complete
precision, harm, all-role cost) plus a new **reading** count: rows whose output violates a requirement quoted in
their own ledger. Then untouched held-out tasks. A null result is recorded as such.
