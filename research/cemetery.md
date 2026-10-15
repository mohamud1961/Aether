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

## Notes

- Rows are one line each. Numbers are the ones recorded in the sources; where a source gives a number as an approximate range, the row keeps the range.
- Several rows are from a branch that is not the checked-out one. Each source comment names the branch or commit.
- Row 17 sits in the Downloads folder, outside the repository.
