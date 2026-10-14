# Task card: noisy open workflow (v2)

Admission: **capability**. Controls test the v2 design. They do not establish parity with the original trace contract.

## Design (v2)

- Noisy evidence: a structured ticket log (ground truth), a mailbox dump with a stale claim, handwritten notes naming a rehearsal ticket, a stale calendar draft, and an archived September cycle with a different closeout.
- The visible check is shape-only. The grader re-runs it on the report, so the Verification claim is recomputed, not trusted.
- Input files (`evidence/`, `archive/`, `briefing/`, `checks/`) are sealed by hash.

## Controls

- Known-bad: 8 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| distractor_not_rejected | known_bad drops_distractor |
| missing_required_evidence | known_bad omits_evidence_ids |
| wrong_ticket_selection | known_bad picks_sticky_note_ticket, archive_ticket_used; careless fake_it, skip_check |
| wrong_owner_selection | known_bad stale_owner |
| missing_verifier_pass_event | known_bad skips_verification, claims_verification_unrun |
| other_file_modified | known_bad evidence_file_edited |
| missing_closure_report | careless do_nothing, wrong_target |
| missing_final_submission | careless half_done |

Trace-dependent process checks are not established by this final-state grader.
