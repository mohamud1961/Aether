# Context study: what the model saw, per step, and where task knowledge stays live (2026-10-16)

Status: **analysis of archived evidence only** (no VM, no model calls), written while the Codex/ChatGPT reviews of the
matched-repair and serialization tests are pending. Question from the principal: is the remaining gap "really context":
how and where the task instructions, the important things learnt during the task, and the model's own decisions stay
relevant to the model?

Evidence: every archived net-fit row with call logs (GLM: B1, S4–S6, step 4, step 2, matched repair, serialization;
GPT-6-Luna: L1, L2), 82 rows; plus all-task context statistics for B1, S4–S6, L1, L2 and step 4. Requests are rebuilt
byte-for-byte from `core_calls.jsonl` (`aether.core.calls.requests`). Scripts: `ctxaudit.py`, `timeline.py`,
`bind.py` (scratchpad). Graph outcomes are the grader's verdicts on the final files.

## 1. What Core shows the model at each step

| Layer | What it holds | Lifetime |
|---|---|---|
| System prompt | role, tools, context-management doc | pinned |
| Task | the instruction text | **pinned**, always first |
| Editable history | assistant turns + tool results (each ≤ ~11 KB), verbatim | until the model condenses it, or a checkpoint summarises older turns above 30k tokens |
| Reasoning | **only the newest assistant turn's**; older turns' reasoning is dropped (`replay_reasoning="newest"`, both GLM and GPT-6-Luna) | one turn |
| Nothing else | no pinned notes or decisions; anything learnt lives only in visible turns or in files |

## 2. Findings

**F1. The task instruction is never lost on net-fit.** At the step that wrote the final `learned_dag.csv` (64 GLM rows with
their own inference), the request held the pinned task with the `to,from` format block in **64/64**; **0** checkpoints
or context edits in any net-fit row; median input ≈ 9–10k tokens, max 23k (budget 32k). Same on graph-query-catalog, repair-history,
dual-language-build, binary-extract. Compaction occurs only on the two long sequence-design tasks (both models fail those; open).

**F2. Same harness, same context mechanics, different model, different outcome.** GPT-6-Luna (newest-only replay too, no
checkpoints on net-fit) wrote a correct learned graph in **4/4** net-fit rows and solved graph-query-catalog 4/4; GLM's learned graph was
correct in **23/64** (≈ 36%), graph-query-catalog 10/16. Harness-held context is identical in kind; the difference is what the model
holds *internally* while it works.

**F3. GLM's main failure is a short-range binding error, not long-range forgetting.** 26/64 GLM writes reversed every
edge. The clearest case (B1 e1) is inside **one code block**: `edges = [('U','M'), …]` written in (parent, child)
order, matching its reasoning ("U→M"), then six lines later `for c,p in edges: f.write(f'{c},{p}')`. The tuples are
unpacked in the order of the file's columns (`to,from` = child, parent) instead of the order in which they were built.
Same pattern elsewhere: `for to, frm in sorted(edges)`, `columns=["to","from"]` over `model.edges()`.

**F4. GLM reads tabular data by the default A,B = A→B, over the header.** Matched b-generic e1 inspected a broken
start file whose every edge is reversed under its `to,from` header and wrote in its reasoning that its own graph
"matches the previous learned_dag.csv exactly (R,M / U,D / …)", then wrote its file in the same (wrong) convention.
Its final check printed the file and concluded "All files correct".

**F5. When the meaning sits in visible text at the point of use, the error disappears.**
- Graph supplied in the task as "(parent → child)": **0/10** reversed (serialization test), including code paths
  (`for p, c in edges: f.write(f"{c},{p}")`, edge list commented "parent -> child").
- GLM's own graph, rows typed by hand (each row written literally): **0/5** reversed.
- GLM's own graph written by code: tuple order labelled near the write (comment/names) **6/19** reversed; unlabelled
  **20/40** reversed. Labels help but are not sufficient (heuristic classification; noisy).

**F6. GLM's reasoning is mostly gone by the time it writes, but that does not separate right from wrong.** Of the
reasoning GLM produced before the write step, the median ~90% is absent from the write request (only the newest
turn's is replayed; replayed reasoning present in 47/64 write requests, often a short one). Correct and reversed rows
alike made their graph decision in earlier, now-dropped turns (22 vs 25). Replaying all reasoning alone is therefore
unlikely to fix the reversal, though it remains a real loss of working state (and F3 shows the error can occur within a
single turn).

## 3. Refined thesis

"It's all context" holds in a specific form:
- **Harness context** (task, history, tool results) is adequate on these tasks: present, uncompacted, small.
- **Working context** (the model's own bindings: "my tuples are (parent, child)", "column `to` is the child", "the hint
  means R→M") is where GLM fails. These bindings are formed in reasoning or implicit in code, never written down, and at
  the moment of use they are re-derived locally, where the nearest salient order (the output's columns, a row's
  left-to-right reading) wins. GPT-6-Luna holds the same bindings internally with the same harness.
- Every earlier lever acted at the **finish** and restated **task** requirements (read-back, receipt, nudge, check);
  none put the model's **own bindings** next to the **write**. F5 says that is where they work.

So the harness question for a smaller model is not "keep the instruction in context" (it is) but "keep the model's
decisions explicit and adjacent to where they are used", without task-specific code.

## 4. Candidate next steps (proposals only, for review; nothing built or run)

1. **Write-adjacent task text (generic):** when a tool call writes a path the task names, the harness appends the
   task's sentences that mention that path to the tool result (string match on the path; no task knowledge). Tests
   whether re-presenting the format at the write moment fixes F3/F4. Cheap, falsifiable on the net-fit board.
2. **Pinned decisions file (generic):** the model may record decisions/conventions in a notes file that Core pins
   after the task (like the task itself), distinct from the earlier requirement ledger (which restated requirements).
   Tests whether externalised bindings survive.
3. **Named-fields guidance (prompt, generic):** "when data has positional structure (pairs, rows, columns), name each
   position where you define it and write deliverables from named fields". Tests the F5 labelling effect directly.
4. **Replay all reasoning (`replay_reasoning="all"`, exists):** predicted weak for reversals (F6); worth one cheap arm as
   a control for the "lost reasoning" hypothesis.

Each would need a sealed prediction, the net-fit board plus controls that GLM already passes (harm), and GPT-6-Luna as the
reference for "a model that holds its own context".

## Caveats

GPT-6-Luna n = 4 on net-fit. The labelled/unlabelled split is a regex heuristic over code near the write. "Reversed" is read from
the grader's extra edges (edges into U). Correlations here are observational; F5's supplied-graph result is the only
controlled comparison.

## Amendment 1 — review corrections (Codex audit `OPUS_CONTEXT_STUDY_AUDIT_20261016.md`, ChatGPT), accepted

Each factual point below was re-checked against the archive before acceptance.

1. **Denominator.** The full GLM inferred/repair population is **68 rows, 24 learned-graph correct**. My 64/23 silently
   excluded 4 rows where the extractor found no write: `s5-…-x2-e1` (correct), `s5-…-x2-e2` (other), `s6-…-x2r-e1`
   and `-e2` (reversed). Percentages in F2/F3/F5 refer to the 64-row write-extracted subset.
2. **"0 context edits in any net-fit row" is false.** 3 accepted model edits: `p2a-net-fit-coreb1-e2` (2) and
   `rp1m-repair-bn-k1-check-coreb1-e3` (1). Automatic checkpoints: 0 (stands). **"Compaction only on the two long
   tasks" is false**: accepted context events also occur on cipher-diff-attack (4 rows) and credential-recovery (1 row, a checkpoint). My
   all-task census omitted the step-2/matched archives and counted only checkpoints.
3. **GPT-6-Luna is not an isolated test.** L1 used Chat Completions with JSON turns, whose written `analysis`/`plan` fields
   stay in history as ordinary content; L2 used Responses with replayed rationale items. "Same context mechanics" was
   wrong; F2 is an observation (4/4 learned graphs, n = 4, mixed interfaces), not evidence of internal retention.
4. **"Every lever acted at the finish" is false.** The read-back instruction (`tools.py:294`) tells the solver to
   read each delivered file back *after writing it*; the think reminder acts after every turn.
5. **"Bindings are never written down" is false.** `p2a coreb1-e2`'s accepted notes kept explicit tuple conventions
   alongside a wrong graph. Persisted notes can preserve mistakes (a direct risk for proposal 2).
6. **F5's heading overstates.** 6/19 labelled writes still reversed; labels are model-chosen, not assigned. The
   supplied-graph result changes role annotation, authority, search burden and workload together.
7. **Replay-all is not a launchable GLM arm** (`core_arm.py` allows `--core-reasoning all` only with Responses + GPT-6-Luna).
8. **Memory-loss framing withdrawn.** The supported claim (ChatGPT's wording, accepted): GLM can have the relevant
   instructions and data available and still fail to preserve the **semantic roles** of an intermediate
   representation when transferring it into an artifact, sometimes within one code block. This does not explain
   initial misinterpretation, wrong graph selection, intervention errors or every wrong finish.

**Proposals in section 4 are withdrawn as a set.** Next step, if authorised: one single-model diagnostic at the
graph-to-file boundary that holds graph values, authority, workload and resources fixed and varies only positional vs
explicitly named directional roles; fresh graphs, both valid column orders (so "always swap" cannot pass), correct
controls; output checker validated on known-good and reversed fixtures before any call; score serialization, harm,
treatment adherence (from the actual code) and cost separately. Prompt-only guidance and a required named-field
interface are different treatments. Only after that, an end-to-end test under the original task.
