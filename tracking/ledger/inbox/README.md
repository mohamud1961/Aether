# Ledger Inbox

This directory is the raw cross-session handoff area for `RAW_LEDGER_UPDATE` handoffs.

Purpose:

- Preserve material updates from agents working in other threads/sessions
- Keep raw handoffs on disk so the historian can ingest them later
- Avoid direct writes by non-historian agents to the canonical ledger files
- Make the role boundary explicit: agent handoffs are raw inputs, historian files are the ledger

Rules:

- One raw update file per material event
- Files are append-only artifacts; do not rewrite old handoffs
- Other agents write here only via `tracking/ledger/tools/record_update.py`
- The historian reads from here and converts updates into the canonical ledger files in `tracking/ledger/`
- Files here are not reviewed truth; they are raw historian inputs
- Inbox files may be noisier than the canonical ledger; the historian is expected to prune aggressively

Workflow:

1. Agent finishes material work.
2. Agent writes a raw `RAW_LEDGER_UPDATE` file here using the helper script.
3. Historian ingests the raw handoff and updates:
   - `timeline.md`
   - `decisions.md`
   - `failures.md`
   - `claims.md`
   - `open_questions.md`

The inbox is not the ledger itself. It is the durable raw handoff layer between sessions.

Pruning expectation:

- Raw handoffs here can include operational noise.
- The historian should keep only updates that matter to the harness research record.
- Example noise to omit unless it changes research outcomes:
  - formatting-only edits
  - JSON cleanup
  - directory tidying
  - metadata normalization with no effect on evidence or conclusions

Backward compatibility:

- `record_update.py` also accepts legacy `LEDGER_UPDATE` blocks.
- New handoffs should use `RAW_LEDGER_UPDATE`.
