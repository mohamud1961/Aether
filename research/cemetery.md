# Cemetery: mechanisms that were killed

**What this is:** A record of about thirty mechanisms, prompts, guards and claims that were tried and then removed or retired, one line each.
**Key result:** Most kills came from a measurement that did not separate the mechanism from its test: a sentinel that regressed, a verifier that held correct work, a run that never launched, or a control that already passed.
**Why it matters:** The surviving design owes much of its shape to these records. Each row names the evidence that ended the mechanism and the rule it left behind.

| # | Mechanism | What it tried | Evidence that killed it | Lesson |
|---|---|---|---|---|
| 1 | Planner with separate code and review roles (Gen 1) | Planner as external memory, with separate generation and review | No scored result; pivoted between December 2025 and February 2026 | Memory without receipts is not evidence.|
| 2 | Repository context tool (Gen 1) | Budgeted repository slices for each turn | Claimed 40 to 50 percent token saving; no measurement recorded | A saving claim needs a measured baseline.|
| 3 | Nine-role pre-phase (Gen 1) | A role pipeline designed the harness before any code | A phase check passed with its signals missing | Fail closed on missing signals.|
| 4 | Verifier with the answers mounted (Gen 1) | A verifier container that could read the answers | The oracle mount leaked the answers | Verifier isolation is a fixed rule.|
| 5 | Composable blocks over one shell tool (Gen 1 to 2) | Swappable blocks and many narrow runners | Historical; no winning configuration recorded | Fewer variants, each gated by an eval.|
| 6 | Ignored-ID attribution guard (Gen 2) | A post-hoc guard that ignores some IDs | 0 of 2 on target rows | A guard tuned to one tool is not a mechanism.|
| 7 | Combined attribution guard (Gen 2) | Hard-coded argument handling for one tool plus two other guards | 2 of 2 target, but 0 of 1 sentinel; total 6 of 12 across arms | A target win that regresses a sentinel is not a win.|
| 8 | Seven-family winner search (Gen 2) | Find the one family that wins on target rows without sentinel regression | Winner count 0 across seven families | A small set rarely yields a single winner; stop searching for one.|
| 9 | Single-file lean kernel (Gen 2) | Persistent-shell kernel with brittle anchors | Improved one row by hiding evidence; rejected | A pass that hides evidence is not a pass.|
| 10 | Eleven-step synthesised harness (Gen 2) | A whole-harness configuration against baseline on the full suite | Every scored run was invalid (container runtime down); held, not rescored | An invalid run is not a score.|
| 11 | Receipt cockpit with background tools (Gen 2) | A continuous session with background and service tools | The model ignored the background tools; both hard rows 0.0; paused | A tool the model does not use does not help.|
| 12 | Five-homolog gate (Gen 2) | Five local tasks as a gate for the runtime | 5 of 5 on one run; verifier not clean on any scoreable row on the next | One green run is not a gate.|
| 13 | Full-board Gen 2 run | 241 tasks, two attempts each | 216 of 241 first attempts never launched; 5 of 19 valid rows passed | Check launch integrity before comparing rates.|
| 14 | Adaptive Harness Profile as a promotion explanation (Gen 2) | A task profile generated before the solve loop | Replication 1 of 4 against 3 of 4; then no difference on the larger set | A probabilistic advantage, kept as a flagged variant only.|
| 15 | Finish review that saw the solver's claims (Gen 3 to 4) | A reviewer shown the solver's own summary | Caught 10 of 18 wrong finishes, against 15 of 18 claim-free | The reviewer must not see the claims.|
| 16 | Artifact verifier at threshold 0.6 (Gen 4) | Verifier reads artifacts with a lower hold threshold | Caught 25 of 28, with 68 of 208 false holds (33 percent); reverted | Catching more wrong finishes does not help if a third of correct work is held.|
| 17 | Model-authored proof contract (Gen 3) | The architect's proof clauses certified by the compiler | The architect could omit requirements; forensic verdict NOT READY, 20 findings | Authority cannot sit with the model that wrote the plan.|
| 18 | Architect in the production path (Gen 3) | The architect's output decided the harness configuration | Removed 19 August 2026; rubric scores of 9 to 10 out of 10 while outcomes did not improve | Separate authority, not separate personas.|
| 19 | Architect contract variants on mixed-proof families (Gen 3) | Contract variants compared on two families | No variant qualified both families; best single variant 3 of 6 | A freeze rule that fails at screen stops the variant.|
| 20 | Stable context deduplication (Gen 4 candidate line) | Replace repeated prompt blocks with stable references | Prompt -29 percent per call, but steps +50 percent, output tokens +172 percent | Lower input tokens can raise total cost; measure end to end.|
| 21 | Lean solver decision contract (Gen 4 candidate line) | A smaller output schema for the solver | Schema -18.5 percent; output -42.7 percent; calls -12.5 percent; protocol incident | Keep the mandatory contract; the saving came with a protocol failure.|
| 22 | Early native compaction at 8k tokens (Gen 4 candidate line) | Compact context at a low threshold | Total tokens +58.8 percent (profile); +105.1 percent (interactive) | Test compaction thresholds on full runs.|
| 23 | Mandatory completion record (Gen 4 candidate line) | A model-visible completion record required at finish | Killed as a mandatory scaffold | A mandatory scaffold can become the failure.|
| 24 | Solver commitment treatment (Gen 4) | An instruction to commit to a decision | 3 of 9 against 2 of 9 for control; input tokens 46,050 against 22,551 | Nine trials cannot separate those rates; set power first.|
| 25 | Semantic completion review (Gen 4) | A semantic review of completion against a mechanical one | 0 semantic wins; 1 mechanical-only win; 4 ties; 76 calls against 34 | A richer review did not pay for its calls in this pilot.|
| 26 | Remaining-time visibility for deadline tasks (Gen 4) | Show the model its remaining run time | Visibility alone did not rescue the deadline task | Visibility is needed for timing and is not sufficient.|
| 27 | Boundary verification step (Gen 4) | A targeted verification step on one failure target | The control solved the target without the step (ceiling) | Check that the control fails the target before testing the treatment.|
| 29 | Greedy default sampling in open-model runs (Gen 4 candidate) | Temperature 0.0 by default | Identical malformed call repeated 18 times; a 32,000-token runaway in two losses | Set sampling explicitly and audit each row.|
| 30 | Full-history memory control (Gen 4 programme, early October) | A full-history control compared against a memory variant | Silently wiped memory on long runs; both comparisons invalid | A control that changes the variable silently is not a control.|
| 31 | Inert claim-free review arm (Gen 4) | A review component on long runs | Zero provider requests on one run (82 calls, 11.9 million tokens) | A component that never fires is not a control.|

## Notes

- Rows are one line each. Numbers are the ones recorded in the sources; where a source gives a number as an approximate range, the row keeps the range.
- Several rows are from a branch that is not the checked-out one. Each source comment names the branch or commit.
- Row 17 sits in the Downloads folder, outside the repository.
