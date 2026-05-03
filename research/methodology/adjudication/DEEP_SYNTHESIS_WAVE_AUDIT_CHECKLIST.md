# Deep Synthesis Wave Audit Checklist

Use this checklist after each completed Deep Synthesis wave.

Purpose:

- verify that the wave answered its declared question
- verify that coverage claims are honest
- verify that the wave compounded into cumulative artifact state
- decide whether the next planned wave may open

## 0. Packet Discipline

- [ ] The wave used an explicit packet or wave supplement.
- [ ] The wave stayed inside the declared artifact and wave scope.
- [ ] The wave did not quietly change the question it was supposed to answer.
- [ ] The wave did not quietly narrow the corpus.

## 1. Coverage Honesty

- [ ] `coverage_used` lists real repo-local paths actually read in the wave.
- [ ] `coverage_not_yet_used` names real unread path families that still matter.
- [ ] `priority_sources_not_yet_read` is concrete and decision-relevant.
- [ ] High-priority untouched evidence is either justified, queued, or flagged as a blocker.

## 2. Evidence And Claims

- [ ] Major wave claims are traced to concrete evidence paths.
- [ ] Observation and inference are kept distinct.
- [ ] Source-backed claims are not mixed with `behavioral reconstruction`.
- [ ] Contradictions are visible rather than smoothed away.
- [ ] Confidence levels match evidence quality.

## 3. Wave Question Resolution

- [ ] The wave materially answered the bounded question it claimed to answer.
- [ ] The wave produced more than summaries or path lists.
- [ ] The wave surfaced at least one real claim, contradiction, gap closure, or open question that matters downstream.
- [ ] The wave did not pretend to close questions it only sampled.

## 4. Compounding Update

- [ ] The wave principal synthesis exists.
- [ ] The canonical `cumulative_synthesis.md` was updated or explicitly left unchanged with reason.
- [ ] `cumulative_synthesis.md` keeps the accepted-claims state visible.
- [ ] `cumulative_synthesis.md` keeps the contradiction register visible.
- [ ] `cumulative_synthesis.md` keeps the coverage frontier visible.
- [ ] `cumulative_synthesis.md` keeps open questions visible when needed.
- [ ] The wave improved the cumulative artifact state, not just the historical record.

Legacy compatibility note:

- Older split files such as `accepted_claims.md`, `contradiction_register.md`, `coverage_frontier.md`, and `open_questions.md` may still exist as backing detail for legacy waves.
- They are not the canonical carry-forward control surface once `cumulative_synthesis.md` is in place for the artifact.

## 5. Ready-To-Proceed Gate

- [ ] The next planned wave is still the correct next move.
- [ ] No structural blocker surfaced that should send control back to the principal.
- [ ] If the wave is incomplete, the gap is explicit and routed.
- [ ] If the wave promoted any mechanism or failure families, their `exploratory` versus `emerging` versus `decision_ready` status is explicit.
- [ ] The verdict is one of:
  - `pass`
  - `pass_with_warnings`
  - `blocked`

Rule:

- Do not mark a wave `pass` because it produced a long output.
- Mark it `pass` only if it added usable, evidenced, cumulative progress.
