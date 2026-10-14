# Name the closeout ticket for this cycle

You are in the case directory. The cycle is closing and the team needs one closeout target recorded: the
ticket, its owner, the evidence that supports the choice, and the candidates you ruled out. The sources are
mixed in quality. There is a structured ticket log, a mailbox dump, handwritten scan notes, a calendar draft,
the brief, and archived cycles. Some are stale or contradict each other.

Write two files:

- `final/closure_report.md`: a Markdown report with these level-2 headings, in this order:
  - `## Decision`: the closeout ticket ID and its owner.
  - `## Evidence IDs`: the evidence IDs (for example `ev-01`) that support the decision.
  - `## Rejected Distractors`: each candidate you rejected, with the reason.
  - `## Verification`: the verification command you ran and its result.
- `out/final_submission.json`: a JSON object with `report_path` (`final/closure_report.md`), `selected_ticket`,
  `selected_owner` and `verifier_command` (the exact command you ran).

Run the visible check from the case directory and record its result under `## Verification`:

    python3 checks/visible_check.py --report final/closure_report.md

That check confirms the headings are present. It does not check the decision.

Do not change anything under `evidence/`, `archive/`, `briefing/` or `checks/`.

Public dataset identifier: harness-evals-public-37968ddf1a33f00a.
