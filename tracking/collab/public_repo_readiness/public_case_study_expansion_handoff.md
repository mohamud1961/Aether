# Public Case Study Expansion Handoff

- Status: `COMPLETE`
- Originating orchestrator thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Date: `2026-06-16`

## Objective And Scope

Turned the public Aether migration/direct-port skeleton into a concrete,
reviewer-facing case study that shows real engineering outcomes without leaking
private or private-eval-sensitive material.

Scope:

- replace the skeleton framing with a finished public-safe narrative;
- show the engineering loop used for the public story;
- explain the public namespace migration outcome;
- document eval-first smoke packs as evidence gates;
- summarize bounded TS-to-Python direct-port slices;
- record the provenance/license guardrail result;
- add a concise validation table and explicit out-of-scope boundaries;
- update small index links so reviewers can find the case study.

Out of scope:

- runtime code changes;
- eval/full task runs;
- branches, commits, pushes, worktrees, VMs, or containers.

## Files Changed

- `docs/case-studies/aether-migration-direct-port-skeleton.md`
- `docs/case-studies/README.md`
- `docs/README.md`
- `README.md`
- `workflows/ai-native-engineering-showcase.md`

## Summary

The case study is now a concrete public narrative instead of a skeleton. It
describes:

- the problem/context for the public story;
- the engineering loop used to keep slices bounded and evidence-backed;
- the `harness.aether2` / `runner.aether2` namespace outcome;
- the public eval-smoke gate pattern;
- the direct TS-to-Python port slices for hooks/permissions, MCP, skills, and
  subagent handoff;
- the provenance and license guardrail result;
- a validation table that links each slice to public-safe evidence;
- the remaining out-of-scope boundaries.

The public indexes now point at the case study with reviewer-friendly link
text so it is easier to find from the top-level docs and showcase pages.

## Validation

- private-path sweep over the edited public docs
  - result: no machine-local path leaks in the edited public docs
- license wording sweep over the edited public docs
  - result: no matches after the final wording fix
- `git diff --check -- README.md docs/README.md docs/case-studies/README.md docs/case-studies/aether-migration-direct-port-skeleton.md workflows/ai-native-engineering-showcase.md`
  - result: passed
- `python3 tools/aether2_genericity_check.py`
  - result: passed
- link/path review for the updated public indexes
  - result: the case study link text now appears in `README.md`, `docs/README.md`,
    `docs/case-studies/README.md`, and `workflows/ai-native-engineering-showcase.md`

## Review Findings And Dispositions

### Hiring Reviewer

- Finding: the first draft was still a skeleton.
- Disposition: accepted and fixed by writing a finished case study with a
  validation table and concrete evidence links.

### Privacy Reviewer

- Finding: public docs might leak private paths or raw material.
- Disposition: rejected; the public-doc sweep found no machine-local path
  leaks in the edited files, and the case study does not cite raw trajectories,
  raw ledger contents, or hidden grader details.

### Legal / Provenance Reviewer

- Finding: the TS-derived source could be described too loosely.
- Disposition: accepted and fixed; the case study now says the quarantined
  README carried an MIT placeholder claim, treats it as non-authoritative, and
  points to the verified Anthropic notice path instead of claiming MIT.

### Maintainer

- Finding: the public index links needed to be easier to find.
- Disposition: accepted and fixed by updating the top-level docs and showcase
  links while keeping the existing file path stable.

### Overclaim Skeptic

- Finding: the case study might drift into production-readiness or eval
  leadership language.
- Disposition: rejected; the final draft explicitly excludes production
  readiness, eval leadership, universal reliability, and public
  runnability claims.

## Remaining Blockers

None for this slice.

## Exact Next Slice

Publish a second public case study that covers a different capability family,
then link it from the same public indexes so the reviewer story shows more than
one engineering shape.

## External State

- No branch, commit, push, worktree move, VM, container, or eval/full task
  run was created.
- No process or server was left active.

## RAW_LEDGER_UPDATE

- Persisted: `tracking/ledger/inbox/2026-06-16/011859_codex-worker-19_public-case-study-expansion-for-bolder-public-readiness_87d2092ac0.md`

## Thread Send

- Target thread ID: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Tool/mechanism: `codex_app.send_message_to_thread`
- Result: `success`
