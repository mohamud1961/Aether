# Decisions

Architecture, methodology, and experiment decisions with evidence and status.

## D-001 | 2026-03-12 | Six-dimension harness scaffold
- Status: active, provisional
- Summary: Use six swappable harness dimensions as the working decomposition for research and implementation.
- Observations: `AGENTS.md` defines interfaces for orientation, tools, execution, context, verification, and recovery blocks. `research/analysis/lego_dimensions.md` mirrors the same six dimensions and explicitly asks whether dimensions are missing.
- Inference: The six-way split is current project policy, but the repo itself records that it may be incomplete.
- Evidence paths: `AGENTS.md`, `research/analysis/lego_dimensions.md`
- Affected components: `blocks/*`, `runner/*`, `experiments/*`
- Supersedes: none
- Confidence: high that this is the active scaffold; medium that it is the final taxonomy
- Follow-up needed: Revisit after evidence review on policy-program, prompt, and environment-substrate concerns.

## D-002 | 2026-03-24 | Corpus-only BigAI trace analysis
- Status: active
- Summary: Analyze BigAI trajectories without official TerminalBench task source, hidden tests, or raw-bundle mutation, and label findings by evidence strength.
- Observations: `research/analysis/bigai_trace_layer/README.md` explicitly prohibits official task source and hidden tests and defines the output schema. The same README defines confidence labels `observed`, `strong_inference`, and `moderate_inference`.
- Inference: The project chose contamination control and evidence traceability over fuller but riskier reconstruction.
- Evidence paths: `research/analysis/bigai_trace_layer/README.md`, `research/analysis/bigai_trace_layer/output/corpus_summary.json`, `research/analysis/bigai_trace_layer/output/question_answers.json`
- Affected components: `research/analysis/bigai_trace_layer`, downstream synthesis work
- Supersedes: none
- Confidence: high
- Follow-up needed: Document uncovered blind spots where public trajectories cannot answer the research question.

## D-003 | 2026-03-25 | Bucketed source-intake and dedupe pipeline
- Status: active
- Summary: Research intake is organized into bucket-specific collection runs, normalized into structured records, and deduped into accepted manifests.
- Observations: `research/source_finder_prompt_pack/` contains one prompt per bucket plus shared schema and operator docs. `research/intake/normalized/2026-03-25__response_object.json` stores normalized records. `research/intake/normalized/manifests/*__accepted.json` and `research/intake/normalized/dedupe/2026-03-25__dedupe_decisions.json` show accepted outputs and explicit dedupe actions.
- Inference: The repo treats literature and source gathering as a reproducible data pipeline rather than informal note-taking.
- Evidence paths: `research/source_finder_prompt_pack/README.md`, `research/source_finder_prompt_pack/prompts/buckets/`, `research/intake/normalized/2026-03-25__response_object.json`, `research/intake/normalized/manifests/`, `research/intake/normalized/dedupe/2026-03-25__dedupe_decisions.json`
- Affected components: `research/intake`, source acquisition workflow
- Supersedes: none
- Confidence: high
- Follow-up needed: Fill zero-coverage buckets or explicitly narrow scope.

## D-004 | 2026-03-28 | Single-writer historian ledger
- Status: active
- Summary: Ledger files under `research/ledger/` are owned by the historian; other agents report material work via `LEDGER_UPDATE` instead of direct edits.
- Observations: `AGENTS.md` requires material work to be reported to the ledger via `LEDGER_UPDATE`. `research/ledger/README.md` states the historian/ledger agent is the single writer. `research/ledger/historian_agent_prompt.md` assigns ownership of the five ledger files.
- Inference: The project intentionally centralizes project history to reduce drift, duplicate edits, and unsupported retrospective claims.
- Evidence paths: `AGENTS.md`, `research/ledger/README.md`, `research/ledger/historian_agent_prompt.md`
- Affected components: `research/ledger`, collaboration workflow
- Supersedes: none
- Confidence: high
- Follow-up needed: Enforce `LEDGER_UPDATE` usage so future history does not depend on reconstruction.

## D-005 | 2026-03-29 | Persist raw ledger handoffs in a shared inbox
- Status: active
- Summary: Non-historian agents must persist each material `LEDGER_UPDATE` to a unique file under `research/ledger/inbox/` using `research/ledger/tools/record_update.py`.
- Observations: `AGENTS.md` now says chat-only emission is insufficient for work done in another session and requires `python3 research/ledger/tools/record_update.py`. `research/ledger/inbox/README.md` defines the inbox as the raw cross-session handoff layer. `research/ledger/historian_agent_prompt.md` now instructs the historian to inspect the inbox in later sessions. `research/ledger/tools/record_update.py` validates a `LEDGER_UPDATE` block from stdin and writes one unique file per update.
- Inference: This decision closes the cross-session visibility gap without violating the single-writer rule for canonical ledger files.
- Evidence paths: `AGENTS.md`, `research/ledger/README.md`, `research/ledger/inbox/README.md`, `research/ledger/historian_agent_prompt.md`, `research/ledger/tools/record_update.py`
- Affected components: collaboration workflow, `research/ledger`
- Supersedes: none
- Confidence: high
- Follow-up needed: If adoption is inconsistent, add an explicit compliance check in future session prompts or tooling.

## D-006 | 2026-03-29 | Raw handoffs are historian inputs, not ledger entries
- Status: active
- Summary: Non-historian agents produce `RAW_LEDGER_UPDATE` handoffs only; the historian alone writes canonical ledger entries.
- Observations: `AGENTS.md` now requires a `RAW_LEDGER_UPDATE` handoff for historian review and says other agents produce raw historian inputs only. `research/ledger/README.md` and `research/ledger/inbox/README.md` now state that inbox files are raw handoffs, not canonical entries. `research/ledger/historian_agent_prompt.md` now treats inbox files and both `RAW_LEDGER_UPDATE` and legacy `LEDGER_UPDATE` blocks as raw inputs that require review before promotion.
- Inference: This clarifies the role boundary and reduces the risk that an agent-authored handoff will be mistaken for reviewed project history.
- Evidence paths: `AGENTS.md`, `research/ledger/README.md`, `research/ledger/inbox/README.md`, `research/ledger/historian_agent_prompt.md`, `research/ledger/tools/record_update.py`
- Affected components: collaboration workflow, historian process
- Supersedes: none; clarifies D-005
- Confidence: high
- Follow-up needed: Use `RAW_LEDGER_UPDATE` for new handoffs while maintaining backward compatibility for older sessions.

## D-007 | 2026-03-29 | Prune raw handoffs to research-significant events
- Status: active
- Summary: The historian should not mirror every raw inbox handoff; the canonical ledger records only what materially matters to the harness research project.
- Observations: `AGENTS.md` now says formatting-only edits, JSON cleanup, file moves, and routine housekeeping are usually not material on their own. `research/ledger/historian_agent_prompt.md` now includes an explicit relevance filter and says to omit mechanical churn unless it affects findings, methodology, experiment validity, corpus integrity, or reproducibility. `research/ledger/README.md` and `research/ledger/inbox/README.md` now describe the inbox as potentially noisy and the canonical ledger as curated.
- Inference: This decision keeps the ledger paper-useful and prevents operational clutter from obscuring actual research outcomes.
- Evidence paths: `AGENTS.md`, `research/ledger/README.md`, `research/ledger/inbox/README.md`, `research/ledger/historian_agent_prompt.md`
- Affected components: historian process, canonical ledger quality
- Supersedes: none
- Confidence: high
- Follow-up needed: Reassess only if the pruning rule starts hiding reproducibility-relevant operational work.
