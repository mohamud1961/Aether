# Research Ledger

This folder is the auditable history of the project.

Its purpose is to preserve:

- What happened
- Why decisions were made
- What evidence supports those decisions
- What failed
- What remains unresolved

## Ownership

- The historian/ledger agent is the single writer for the main ledger files
- Other agents report material events via raw `RAW_LEDGER_UPDATE` handoffs
- Other agents persist raw handoffs in `tracking/ledger/inbox/` using `tracking/ledger/tools/record_update.py`
- Raw handoffs are inputs for historian review, not canonical ledger entries
- Raw evidence should stay in its source location; the ledger links to it rather than duplicating it
- Collaboration artifacts under `tracking/collab/` may be cited as evidence paths, but they are not canonical ledger entries on their own

## Files

- `historian_agent_prompt.md` - Prompt for the ledger/historian agent
- `inbox/` - Raw persisted `RAW_LEDGER_UPDATE` handoffs from other sessions
- `tools/record_update.py` - Helper to persist one raw update file per material event
- `timeline.md` - Chronological record of significant project events
- `decisions.md` - Architecture, methodology, and experiment decisions
- `failures.md` - Failed hypotheses, regressions, dead ends, and invalid methods
- `claims.md` - Candidate paper claims with supporting evidence and confidence
- `open_questions.md` - Unresolved issues that materially affect the research direction

## Usage

The ledger should be:

- Evidence-linked
- Additive rather than destructive
- Clear about what is observed vs inferred
- Honest about contradictions and uncertainty
- Curated for research relevance rather than mirroring every raw operational update

## Cross-Session Workflow

1. Non-historian agent finishes material work.
2. Agent writes a raw `RAW_LEDGER_UPDATE` handoff with:
   - `python3 tracking/ledger/tools/record_update.py`
   - include `commit_message` using a real one-line commit subject, `HOLD - <reason>`, or `NONE - no tracked file changes`
3. The helper creates a unique file in `tracking/ledger/inbox/YYYY-MM-DD/`.
4. A later historian session reads the inbox, reviews the raw handoff, and promotes supported updates into the canonical ledger files.

Historian pruning rule:

- The inbox may contain noisy operational updates.
- The canonical ledger should record only what materially affects this research project:
  - research findings
  - methodology
  - experiment validity
  - implementation changes that affect the harness research program
  - corpus integrity
  - reproducibility
  - decisions, failures, contradictions, and open questions
- Mechanical churn such as formatting-only edits or JSON cleanup should usually be omitted unless it changes one of the categories above.

Backward compatibility:

- The recorder also accepts legacy `LEDGER_UPDATE` blocks.
- New handoffs should use `RAW_LEDGER_UPDATE` so the role boundary stays explicit.
