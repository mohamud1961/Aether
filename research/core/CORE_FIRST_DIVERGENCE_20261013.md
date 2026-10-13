# First-divergence comparisons: B1 (Aether Core) vs T1 (Terminus 2), GLM-5.3-Flash

Date: 2026-10-13. Cost: £0 (existing traces only). Method: for each wrong
outcome, find the first turn where the run committed to the wrong belief, state
what the model had in front of it at that point, and name the check that would
have exposed the error. Sources: `audit_output/aether_b1_20261013/`,
`audit_output/aether_t1_20261013/`, task tests under `official_tasks/`.
Follows the form of GPT-6-Astra's credential-recovery and graph-query comparisons (S2 audit).

## net-fit

Task rule: for ambiguous non-U edges, "the node labeled with the letter that
comes first in the alphabet is the child". Output header `to,from`; the grader
reads columns by name. Truth includes R→M (M is the child).

| Run | Result | First divergence | Visible to the model? |
|---|---|---|---|
| B1 e1 | fail | Right graph in reasoning (R→M). The writer loop unpacked `(parent, child)` tuples as `(c, p)`, so every row was reversed. The run printed the file: `to,from / U,M / ...`, which says U has a parent, against the stated "U has no parents". | Yes: printed output |
| B1 e2 | fail | Turn 21 reasoning: "R comes before M, so child = R". A letter-order slip. Carried to finish unchanged. | Yes: own reasoning |
| T1 e1 | fail | Correct at step 6 (M child of R). At step 7 it flipped to "R first … M→R" and kept that through the confirmation prompt. | Yes: own reasoning |
| T1 e2 | **pass** | Wrote explicit letter positions ("D 4th, M 13th, R 18th") and re-derived the rule again at the confirmation prompt. | n/a |

All four runs quoted the rule correctly. None of the three failures came from
not knowing the rule. They were mechanical slips (letter order, tuple order),
and each one shows up as soon as the rule or the file is *computed* instead of
asserted: `sorted(["M","R"])`, or reading the written CSV back by its own
header and checking "U has no parents".

## construct-assembly

The grader message "must be in the order flag–donor–dhfr–acceptor–snap" is
misleading. It fires because `find()` returned −1 for a component; the order
itself was correct in both runs. **This corrects my earlier summary, which said
the runs claimed the wrong order.**

The donor in the reference is the full 5WJ2 PDB FASTA, minus the leading M, with
the chromophore `X` expanded to Clover's precursor **GYG**.

| Run | Result | First divergence | Visible to the model? |
|---|---|---|---|
| T1 e2 | fail | Expanded the 5WJ2 `X` to **TYG** (wtGFP's chromophore) from memory: `entity('5WJ2','TYG')`. Clover has T65G, so the right expansion is GYG. FPbase's Clover sequence was in reach, but the run's "independent validation" compared the gBlock against its own expansion. | Retrievable, not consulted |
| B1 e2 | fail | Turn 29 settled on X→Y (single residue; the donor is 257 aa against 259). The finish claims "X→GYG/MYG resolved". The final reasoning also lists linkers of "38, 16, 10, 14 aa (within 5–20)". | Yes: own code and reasoning contradict the claim |
| T1 e1, B1 e1 | fail | No `gblock.txt` written (timeout / no file). | n/a |

No construct-assembly run passed, so there is no passing contrast here.

## seq-assembly (the timeout case)

| Run | Result | First divergence |
|---|---|---|
| T1 e1 | timeout | Spent 25 turns on validation scripts and timed out before writing `primers.fasta`. |
| T1 e2 | timeout, file present | Primers in **uppercase**. The grader does a case-sensitive `find("ggtctc")`. The task never states a case; the input FASTA is lowercase. This is an unstated convention (grader brittleness), not a false finish of a stated requirement. Also hit the time limit. |
| B1 e2 | fail | All four reverse primers carry `gagacc` (the BsaI site in the wrong orientation), so BsaI would cut away from the insert. This is a real design error. A digest-and-assemble simulation from the written primers (which T1 e2 ran) would expose it. |
| B1 e1 | harness error | RuntimeError; no grade. |

## Pattern across the three tasks (plus GPT-6-Astra's two)

- **Visible but unchecked.** In 6 of the 7 graded wrong outcomes above, the error was visible in the run's own context (reasoning, printed output, or code) or could be detected from data the run already had. The exception is the seq-assembly uppercase case, which turns on an unstated convention.
- **The same holds for GPT-6-Astra's comparisons.** In credential-recovery, the run saw len=14 and claimed 23. In graph-query, two separate conditions were bound to one variable.
- **The failed self-checks were circular.** Each checked the artifact against the run's own built expectation (its own chromophore expansion, its own tuple list, its own BIC winner). None checked against the stated requirement or an external source.
- **The passing contrast differs by method, not length.** T1 e2 on net-fit re-derived the rule explicitly from first principles. The S2 finding (deliberation volume does not separate right from wrong) is consistent with this.
- **Harness asymmetry is small here.** Both harnesses make the same kinds of slips. Terminus's edge on this board is not explained by these cases. Its passes came from runs that happened to re-derive, plus timeouts that cost both harnesses.

## Implication for the next mechanism (proposal only, not built)

The missing behaviour is a **computed check of the artifact against the stated
requirement or an external source**. Asserted checks and self-built oracles
don't count.

Generic candidate:
- When the solver declares a requirement met, it shows the command whose output proves it on the artifact.
- The verifier re-runs that command on the task state and compares it against the task text, using read-only tools.

Before any board run, test this on public-contract homologs:
- the net-fit tie rule and CSV semantics;
- a chromophore or sequence match;
- a site-orientation case.

Include false-objection controls, where a correct state must not be held.

Risks:
- **A1 showed that prewritten checks harm correct states (42%).** The check has to be the solver's own, run on the artifact, not a harness-authored contract.
- **"A stronger model would do this itself."** That test applies. The open question is whether this is workbench (a cheap way to show proof) or crutch.

Gate: GPT-6-Astra review before building.

## Not done / caveats

- These are single traces per cell. The pattern is qualitative, not a rate.
- seq-assembly B1 e1 is a harness RuntimeError and is excluded from the 7.
- The json_turn strict-validity reclassification for the S2 bench (GPT-6-Astra item) is still pending.
