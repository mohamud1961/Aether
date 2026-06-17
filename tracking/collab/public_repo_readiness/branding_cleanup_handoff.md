# Branding Cleanup Handoff

- Status: `COMPLETE`
- Originating orchestrator thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Date: `2026-06-16`

## Objective And Scope

Performed a focused public-surface branding cleanup after the direct TS-to-
Python port chain. The goal was to separate legitimate provenance/source
references from product-surface branding leaks, neutralize the latter where
safe, and preserve compatibility behavior for source-derived names.

Out of scope:

- deleting or rewriting quarantined source trees;
- removing legitimate provenance references;
- changing runtime behavior beyond compatibility-preserving naming clarity.

## Scan Method

Final public-surface scan command:

```bash
rg -n -i -e 'claude\\.ai|\\.claude|anthropic|claude' README.md docs workflows harness/aether2 tests tracking/collab/public_repo_readiness eval_suite --glob '!**/stage_02_synthesis/**' --glob '!tracking/ledger/**'
```

The scan covered likely public paths only. It excluded the private research
analysis tree and the raw ledger, so the counts below describe the reviewer-
facing surface rather than the whole repository history.

## Final Scan Summary

- Total public-surface matches: `200`
- Legitimate provenance/source references: `8`
- Source-map / handoff references: `172`
- API / compatibility references copied from the TS port: `18`
- Unrelated public references that are not branding leaks: `2`
- Public-surface branding leaks remaining after cleanup: `0`

Notes:

- the `172` source-map/handoff hits include the `tracking/collab/public_repo_readiness/claude_ts_*` files plus the explicit cross-links from the case-study and workflow pages;
- the `18` compatibility hits are the expected `.claude` directory references, `omit_claude_md`, and `claude.ai` MCP normalization behavior;
- the `2` unrelated hits are `ANTHROPIC_API_KEY` in a test and the `_CLAUDEAI_SERVER_PREFIX` call site in MCP normalization; neither requires product branding changes.

## Classification Policy

- `legitimate provenance/source reference`: explicit provenance notes, license
  caveat docs, or source-tree references that must remain visible.
- `source-map / handoff reference`: public-readiness docs, case-study links,
  and workflow links that point to the direct-port evidence trail.
- `product-surface branding leak`: public docs, workflow prose, or docstrings
  that make HarnessEng/Aether read like a Claude-branded product.
- `API / compatibility field copied from TS`: source-derived paths or field
  names that should remain stable unless a backward-compatible alias is added.
- `private/research surface`: non-public research or synthesis materials that
  should be excluded from publication rather than rewritten here.

## Exact Files Changed

- `harness/aether2/skills/loader.py`
- `harness/aether2/skills/registry.py`
- `harness/aether2/hooks/lifecycle.py`
- `harness/aether2/tools/permissions.py`
- `harness/aether2/tools/mcp.py`
- `harness/aether2/agents/loader.py`
- `harness/aether2/hooks/README.md`
- `harness/aether2/tools/README.md`
- `harness/aether2/agents/README.md`
- `docs/publication/publication_gap_list.md`
- `workflows/skills/nate-derived-skill-map.md`
- `tracking/collab/public_repo_readiness/ai_native_showcase_handoff.md`

## What Branding Was Removed Or Renamed

- Reworded runtime/docstring prose from `claude-code_ts_release` / `Claude TS`
  to neutral source language such as `quarantined external TypeScript source
  tree` and `quarantined TS source`.
- Reworded the tools/agents/hooks README prose to describe source-adapted
  substrate without presenting HarnessEng as a Claude-branded product.
- Replaced the `Claude vs. Codex` wording in the Nate-derived workflow skill
  map with `source-vs-HarnessEng`.
- Neutralized publication-gap prose that still implied the public story should
  be framed as `Claude TS` instead of a quarantined source-derived port slice.
- Clarified the showcase handoff language so the public position reads as
  `quarantined TS-derived` rather than Claude-branded in prose.

## What Branding Intentionally Remains And Why

- `tracking/collab/public_repo_readiness/claude_ts_*` filenames remain intact
  as provenance markers and direct-port handoff links.
- `.claude` directory discovery in `harness/aether2/skills/loader.py` and the
  matching tests remain as source-derived compatibility behavior.
- `omit_claude_md` remains as a serialized compatibility field in
  `harness/aether2/agents/loader.py`; no alias was needed for this cleanup
  slice, and changing it would risk compatibility churn.
- `claude.ai` MCP normalization remains in `harness/aether2/tools/mcp.py`
  because it is part of the TS-derived normalization contract and has a
  dedicated compatibility test.
- Provenance docs under `docs/provenance/` still name the quarantined source
  tree and upstream licensing caveat because that is the point of those docs.

## Validation Commands And Results

- `python3 -X pycache_prefix=/tmp/harnesseng_pycache -m py_compile harness/aether2/skills/loader.py harness/aether2/skills/registry.py harness/aether2/hooks/lifecycle.py harness/aether2/tools/permissions.py harness/aether2/tools/mcp.py harness/aether2/agents/loader.py`
  - Result: passed
- `python3 tools/aether2_genericity_check.py`
  - Result: passed
- `git diff --check -- README.md docs workflows harness/aether2 tests tracking/collab/public_repo_readiness eval_suite`
  - Result: passed
- Final public-surface branding scan command above
  - Result: passed with the counts listed in the scan summary
- `~/.codex/skills/codex-review/scripts/codex-review --mode local`
  - Result: blocked by local Codex runtime state (`attempt to write a readonly database` / `Operation not permitted`)

## Review Findings And Dispositions

- Hiring reviewer:
  - accepted; the public surface no longer reads like a Claude clone in prose.
- Provenance reviewer:
  - accepted; explicit provenance notes and direct-port handoff references
    remain accurate, and the `claude_ts_*` artifacts are still clearly framed
    as source-map evidence.
- Maintainer:
  - accepted; compatibility names were preserved instead of being renamed in a
    way that could break serialization or tests.
- Codex review helper:
  - no actionable findings were produced because the helper could not start in
    this environment.

## Remaining Branding / Publication Gaps

- The upstream `LICENSE` / notice text for the quarantined TS-derived port
  slices is still not recovered here.
- The public-readiness handoff set still contains explicit source-map
  references, which is intentional but still requires provenance awareness.
- A broader public-surface privacy pass over the non-readiness docs/workflows
  remains available as a follow-up if we want to keep reducing provenance
  vocabulary in the surrounding narrative.

## Exact Next Dependency-Ready Slice

Recover and verify the upstream `LICENSE` / notice text for the quarantined
TS-derived port slices, then finalize the third-party notice package that the
public readiness docs are already pointing at.

## External-State Confirmation

- No branch, commit, push, or worktree move was created.
- No VM/container lifecycle action was started.
- No credentials or network-only proprietary surface were touched.
- Unrelated dirty-tree changes were preserved and left untouched.

## Persisted RAW_LEDGER_UPDATE

- `tracking/ledger/inbox/2026-06-16/004932_branding-cleanup-worker-15_public-surface-branding-cleanup-after-the-direct-ts-to-python-port-chain_81f4ee8aa2.md`

## Thread Send

- Target thread ID: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Result: `success via codex_app.send_message_to_thread`
