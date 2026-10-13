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

The donor in the reference is the full tagged 5WJ2 PDB FASTA, minus the leading
M, with the chromophore `X` expanded to Clover's precursor **GYG**.

| Run | Result | First divergence (corrected after GPT-6-Astra review) |
|---|---|---|
| T1 e2 | fail | **Obtained evidence, then ignored it.** The step 13 terminal observation already showed the chromophore as GLY-TYR-GLY. At step 14 the run chose `entity('5WJ2','TYG')` (wtGFP). Its validation compared the gBlock against its own expansion. |
| B1 e2 | fail | Turn 65 says it will use the full tagged PDB FASTA. In fact it built from the 239-aa FPbase Clover and mCherry strings (`[flag, clover, dhfr, mch, snap]`), so the tagged PDB donor is absent. It also stripped SNAP's first residue unconditionally (`f3[1:]`), even though 3KZY has no leading M. Its final reasoning lists linkers of 38 aa ("GS"×19) as "within 5–20", and the final request contained the actual component positions. **My first version said "X→Y in code"; that was wrong.** The 257-aa string I matched was an intermediate, not the build. |
| T1 e1, B1 e1 | fail | No `gblock.txt` written (timeout / no file). |

No construct-assembly run passed, so there is no passing contrast here.

## seq-assembly (the timeout case)

| Run | Result | First divergence (corrected after GPT-6-Astra review) |
|---|---|---|
| T1 e1 | timeout | Spent 25 turns on validation scripts and timed out before writing `primers.fasta`. |
| T1 e2 | timeout, file present | **My uppercase attribution is disproved.** The grader lowercases primers (the task tests). The real failure: all four reverse primers carry <seq>; the forwards carry <seq>. At step 18 the run switched the reverse template from <seq> to <seq> (the earlier design had also failed assembly). Step 22's "simulation" built the product end as `...+'A'+'<seq>'+rc(rclamp)` instead of deriving it from the actual reverse primer, so it passed its own wrong physical model. NEB's E1601 manual uses <seq> 5′→3′ in both amplification primers. **T1 is not a successful-simulation contrast.** |
| B1 e2 | fail | Same error: all four reverse primers carry <seq>. |
| B1 e1 | not graded | Provider/protocol RuntimeError. |

Both harnesses made the same site-orientation error.

## net-fit extension (after GPT-6-Astra review)

- **B1 e1:** the error is not only in the writer. `G.add_edge(p, c)` on `(parent, child)` tuples also reversed the sampling traversal, while the CPDs used the original parents.
- **T1 e1:** at steps 8–9 it sometimes states "M child of R" correctly, yet equates that with the opposite parents map. The contradiction persists.
- **T1 e2's pass supports a hypothesis, not a causal proof:** no new commands ran at the confirmation step.

## Denominators (corrected)

12 scheduled cells across the three tasks:

| Outcome | Count |
|---|---|
| Graded | 11 |
| Pass | 1 |
| Normal finishes, wrong | 6 |
| Graded timeouts | 4 |
| Ungraded (provider/protocol failure) | 1 |

My earlier "6 of 7" took the 6 wrong finishes plus the artifact-bearing T1 seq-assembly timeout, and left out the other 3 graded timeouts.

Corrected statement:
- In all 6 normal wrong finishes, the critical error was visible in the run's own context, or in evidence it had already obtained.
- **Not all checks were circular.** The GC-window and oligotm checks were real and useful. What failed was the critical assumption, or the check's coverage of it.
- **A1 correction:** prewritten checks raised false objections on 10 of 24 correct states. They did not destroy 42% of correct results.

## Mechanism verdict (GPT-6-Astra: conditional workbench, not ready as written)

- **Same-command replay proves only execution and reproducibility, not semantic correctness.** construct-assembly's GS-repeat checker and seq-assembly's fabricated product both pass reproducibly with bad artifacts.
- **Revised candidate:**
  - The solver chooses a check that can falsify its important assumption, using the actual delivered bytes plus task or source evidence.
  - It resolves contradictions it has already observed.
  - Existing receipts are reused.
- **Excluded:** no mandatory proof command for every claim, no universal holds, no prose quotas, and generated checks are not treated as infallible.
- A source-aware reviewer is a separate, later treatment, and only if the solver-only step earns value.

Minimum design, all free:

1. Finish the S2 protocol strict-validity reclassification and this correction.
2. Offline real-file controls:
   - stale or wrong-path receipts;
   - circular success;
   - an unavailable or failed checker;
   - deadlines;
   - candidate mutation attempts, alongside legitimate scratch writes;
   - an isolated candidate snapshot, writable scratch space, and bounded execution for any rerun.
3. 12 discrimination states: 4 public-contract families × (1 bad + 2 allowed-correct alternatives). Fixtures stay in evals, not Core. The families:
   - representation/units;
   - reference identity/version;
   - transform direction with an independent decoder;
   - independent-vs-same-object existential conditions.

Gate: any paid diagnostic needs explicit user authorization and a cost seal. GPT-6-Astra's suggested maximum is 16 short restored-state episodes (baseline vs one solver-only treatment, 4 bad + 4 good per arm), not 16 full public tasks.

## Not done / caveats

- These are single traces per cell. The pattern is qualitative, not a rate.
- The json_turn strict-validity reclassification for the S2 bench (GPT-6-Astra item) is still pending.
