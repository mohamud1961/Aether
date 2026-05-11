# Accepted Corpus Local-Capture Audit

Date: 2026-03-31
Scope: `research/intake/normalized/2026-03-25__response_object.json`, `research/intake/records/`, `research/sources/docs/`, `research/sources/papers/`, `research/sources/threads/`

## Bottom line

The accepted corpus is mostly metadata shells.

- Accepted sources audited: 103, from `research/intake/normalized/2026-03-25__response_object.json`
- `captured_and_linked`: 2
- `captured_but_unlinked`: 0
- `not_captured`: 79
- `malformed_or_suspicious`: 22

The full per-source classification is in `research/analysis/2026-03-31__accepted_corpus_local_capture_audit.tsv`.

## What is actually captured

Only two accepted sources have an explicit normalized-to-local capture link:

1. `src_pap_904b76036b1c`
   - Accepted record: `research/intake/records/src_pap_904b76036b1c.json`
   - Normalized link: `research/intake/normalized/2026-03-25__response_object.json` (the `capture_metadata_matches` block under `src_pap_904b76036b1c`)
   - Backing artifact: `research/sources/papers/src_pap_dd4ca3841fb4/capture.json`
2. `src_pmt_f4ab21a8c943`
   - Accepted record: `research/intake/records/src_pmt_f4ab21a8c943.json`
   - Normalized link: `research/intake/normalized/2026-03-25__response_object.json` (the `capture_metadata_matches` block under `src_pmt_f4ab21a8c943`)
   - Backing artifact: `research/sources/docs/src_doc_9fa759b72385/capture.json`

Even these two are only linked in the normalized file. Their per-record JSON files still carry null capture linkage fields:

- `research/intake/records/src_pap_904b76036b1c.json`
- `research/intake/records/src_pmt_f4ab21a8c943.json`

So the accepted corpus has only 2 linked captures, and 0 clean cases where a source is already locally captured but merely missing normalized linkage.

## Major defects

### 1. Accepted corpus is overwhelmingly uncaptured

79 accepted sources have backing record files under `research/intake/records/` but no matching local artifact under `research/sources/docs/`, `research/sources/papers/`, or `research/sources/threads/`.

The largest uncaptured buckets are:

- `state_management`: 20
- `agent_architecture`: 17
- `context_engineering`: 13
- `tooling_tool_gateway`: 11
- `verification_completion`: 9
- `policy_program`: 8

The largest uncaptured source types are:

- `official_doc`: 27
- `issue_thread`: 18
- `paper`: 18
- `engineering_writeup`: 13
- `repo`: 3

All 18 accepted `issue_thread` sources are uncaptured. The thread source tree contains no thread artifacts at all, only `research/sources/threads/.gitkeep`.

### 2. 22 accepted sources are malformed or suspicious

These 22 accepted IDs have no backing record file under `research/intake/records/`. They are listed in the TSV as `malformed_or_suspicious`.

Representative examples:

- `src_art_2c3d4e5f6g7h` in `research/intake/normalized/2026-03-25__response_object.json`, but no `research/intake/records/src_art_2c3d4e5f6g7h.json`
- `src_sep_9901d8c1a011` in `research/intake/normalized/2026-03-25__response_object.json`, but no `research/intake/records/src_sep_9901d8c1a011.json`
- `src_pap_ef56gh78ij90` in `research/intake/normalized/2026-03-25__response_object.json`, but no `research/intake/records/src_pap_ef56gh78ij90.json`

`src_pap_ef56gh78ij90` is the clearest quarantine case:

- The accepted normalized entry exists in `research/intake/normalized/2026-03-25__response_object.json`
- There is no accepted record file under `research/intake/records/src_pap_ef56gh78ij90.json`
- The normalized entry points to an existing capture under a different source ID: `research/sources/papers/src_pap_35d84f1edd93/capture.json`

That is not a capture gap. It is accepted-ID corruption.

### 3. Provenance fields are malformed in-place

Many accepted normalized records store markdown links inside JSON provenance fields instead of plain URLs. Representative examples:

- `research/intake/normalized/2026-03-25__response_object.json` under `src_doc_384400cfab11`
- `research/intake/normalized/2026-03-25__response_object.json` under `src_pap_904b76036b1c`
- `research/intake/normalized/2026-03-25__response_object.json` under `src_pmt_f4ab21a8c943`

These malformed `original_canonical_url` values should not be treated as reliable linkage data.

### 4. The capture tree itself has orphan paper artifacts

The paper source tree also contains six `artifact.pdf` files with no sibling `capture.json`:

- `research/sources/papers/src_pap_18c026130067/artifact.pdf`
- `research/sources/papers/src_pap_7034b3af9095/artifact.pdf`
- `research/sources/papers/src_pap_7a00775580ac/artifact.pdf`
- `research/sources/papers/src_pap_bbcb7d09e1cf/artifact.pdf`
- `research/sources/papers/src_pap_c0164575037f/artifact.pdf`
- `research/sources/papers/src_pap_d87e929adbb6/artifact.pdf`

Those files are outside the accepted-corpus crosswalk, but they show the local capture tree is not internally clean either.

## Smallest repair plan

### A. Metadata linkage repair only

There are no strict `captured_but_unlinked` accepted sources.

There are only two repairable linkage cases, and both are already linked in the normalized corpus but not propagated into the per-record JSON:

1. Propagate the normalized capture link for `src_pap_904b76036b1c` into `research/intake/records/src_pap_904b76036b1c.json`
2. Propagate the normalized capture link for `src_pmt_f4ab21a8c943` into `research/intake/records/src_pmt_f4ab21a8c943.json`

### B. Reject or quarantine

Quarantine the 22 `malformed_or_suspicious` accepted IDs in the TSV before doing any backfill work.

Highest-priority quarantine examples:

1. `src_pap_ef56gh78ij90`: duplicate accepted ID with a real capture already living under `src_pap_35d84f1edd93`
2. `src_sep_9901d8c1a011`: accepted with no backing record file
3. `src_sep_ca66b02a33ff`: accepted with no backing record file
4. `src_art_5f6g7h8i9j0k`: accepted with no backing record file
5. `src_bnm_webarena444`: accepted with no backing record file

### C. Actual local capture backfill

Backfill the smallest first wave against decision-critical sources that already have accepted record files and high decision relevance:

1. `research/intake/records/src_doc_54d4071243dd.json`
   - Capture target: `https://platform.claude.com/docs/en/build-with-claude/compaction`
   - Why first: core context compaction policy input
2. `research/intake/records/src_doc_9a3bbc4f637b.json`
   - Capture target: `https://platform.claude.com/docs/en/build-with-claude/prompt-caching`
   - Why first: core token/cost policy input
3. `research/intake/records/src_doc_118b78fe9c63.json`
   - Capture target: `https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints`
   - Why first: checkpoint and resume semantics
4. `research/intake/records/src_doc_9f8e7d6c5b4a.json`
   - Capture target: `https://langchain-ai.github.io/langgraph/concepts/persistence`
   - Why first: persistence and state recovery semantics
5. `research/intake/records/src_doc_5c76d18b4059.json`
   - Capture target: `https://modelcontextprotocol.io/specification/2025-11-25/client/roots`
   - Why first: workspace/root exposure policy
6. `research/intake/records/src_doc_78e1a708df4a.json`
   - Capture target: `https://modelcontextprotocol.io/specification/2025-11-25/server/tools`
   - Why first: tool surface and result-shape policy

If a seventh slot is available, use:

- `research/intake/records/src_cod_87b73c75d11a.json`
  - Capture target: `https://github.com/openai/codex/blob/main/codex-rs/core/codex-max-prompt_prompt.md`
  - Why first: direct policy-program evidence

## Conclusion

The accepted corpus should not currently be treated as a locally captured evidence base.

Under a strict local-artifact test, 101 of 103 accepted entries are not cleanly linked to a real local capture, and 22 of those 101 are structurally malformed before capture coverage is even considered.
