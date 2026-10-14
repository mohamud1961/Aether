# Ceiling: noisy_open_workflow (v2)

## What a perfect solution does

1. Reads `evidence/tickets.jsonl` as the source for final-cycle membership. The final-cycle rows are
   `ev-02` and `ev-03`, both for `OPS-447`, owner `dax`.
2. Reconciles the noise against the log without letting it decide:
   - `evidence/mailbox_dump.txt` says OPS-440 "looked done early" and that the final cycle "moved to OPS-447". The
     mail supports the log, and its OPS-440 is not the answer.
   - `evidence/handwritten_scan_notes.txt` names `OPS-499`, from a rehearsal board. It is not in the log.
   - `briefing/cycle_calendar.md` (a draft, last updated 2026-09-28) names OPS-440. It is stale.
   - `archive/tickets_2026-09.jsonl` shows OPS-440 as the September closeout. Archived cycles are context only.
3. Writes `final/closure_report.md` with the four required sections. `## Decision` names OPS-447 and dax. The
   evidence lists `ev-02` and `ev-03`. The rejected distractor section names OPS-499, with the reason.
4. Runs `python3 checks/visible_check.py --report final/closure_report.md`, records the pass, and writes
   `out/final_submission.json`.
5. Leaves `evidence/`, `archive/`, `briefing/` and `checks/` byte-identical.

## Why each known-bad state is wrong

- `drops_distractor.sh`: the rejected section no longer names OPS-499. Grader: `distractor_not_rejected`.
- `omits_evidence_ids.sh`: `ev-02` and `ev-03` are missing from the evidence section. Grader: `missing_required_evidence`.
- `picks_sticky_note_ticket.sh`: the decision follows the handwritten note (OPS-499). Grader: `wrong_ticket_selection`.
- `archive_ticket_used.sh`: the decision follows the September archive (OPS-440, mira). Grader: `wrong_ticket_selection`.
- `stale_owner.sh`: right ticket, owner taken from the wrong row (mira). Grader: `wrong_owner_selection`.
- `skips_verification.sh`: no pass is recorded and the verifier command is blank. Grader: `missing_verifier_pass_event`.
- `evidence_file_edited.sh`: the report is right, but the structured log was rewritten to fit it. Grader: `other_file_modified`.

## Careless controls

- `do_nothing.sh`: `missing_closure_report`.
- `fake_it.sh`: a complete-looking report from the calendar draft and the archive. `wrong_ticket_selection`.
- `skip_check.sh`: the first final-cycle row of the September archive, never checked against the live log. `wrong_ticket_selection`.
- `wrong_target.sh`: the report is written under `report/`, not `final/`. `missing_closure_report`.
- `half_done.sh`: the report is right, the submission is never written. `missing_final_submission`.

## Limits

The grader accepts a `VISIBLE_PASS` line in the verification section; it does not re-run the check. The
verification section is a claim, not evidence. The known-bad `skips_verification` covers its absence.

## Grader expectations

- Reference: `passed: true`.
- Untouched workspace: `missing_closure_report` and `missing_final_submission`.
- Every known-bad fails with its `# expect:` code in `reasons`.
