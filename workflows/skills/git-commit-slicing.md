# Git Commit Slicing

Use this skill when completed, coherent slices of work need to be turned into
regular, intentional commits.

This skill is the public-safe version of the repo's commit discipline. It is a
workflow skill, not a product feature. Its job is to preserve a clean development
narrative across a multi-worker, multi-session build.

## Governing Question

> What is the smallest coherent commit that can be made from the current
> worktree?

"Smallest coherent" means:

- one logical slice of work;
- accurate commit message;
- no unrelated files bundled in;
- no destructive history rewriting.

A giant terminal commit that dumps a day's work is not coherent. A commit that
mixes three unrelated changes is not coherent.

## When To Use

Use this skill when:

- a slice of implementation work is complete and ready to checkpoint;
- the worktree has accumulated multiple changes that need to be separated;
- a worker handoff says "ready to commit" and the diff needs validation;
- you need to produce a split plan because the diff is mixed.

Do not use this skill for:

- interactive rebase or history rewriting (never do this by default);
- force-pushing (never do this without explicit instruction);
- committing work that is still flagged as partial or blocked in the handoff.

## Workflow

### 1. Inspect the Worktree

Run:

```
git status --short
git diff --stat
git diff --cached
git diff
```

Also inspect:

- `<project>/tracking/ledger/inbox/` raw handoffs for commit intent and rationale;
- prior git handoff reports if they exist.

### 2. Cluster Files into Commit Candidates

Group changed files by intent:

- all files that implement one logical slice together;
- test files go with the production files they test;
- schema/config changes go with the feature they enable;
- documentation changes can go with the feature or stand alone if substantial.

A commit candidate is the smallest logical group where a reader can understand
why these files changed together.

### 3. Classify Each Candidate

Assign one of:

- `committed`: already in history; nothing to do.
- `commit_ready`: coherent, complete, safe to stage and commit now.
- `split_required`: files need to be separated before committing.
- `blocked`: something prevents committing this slice (unclear intent,
  partial implementation, mixed ownership).

### 4. For Commit-Ready Candidates

```
git add <files for this slice>
git diff --cached   # verify staged diff is coherent
git commit -m "<imperative subject line>"
```

Commit message rules:

- imperative mood: "add", "fix", "repair", "remove" — not "added" or "adding"
- specific subject: `runtime: repair finalize trigger semantics` not `updates`
- optional scope is good: `<area>: <what changed>`
- the message must describe the actual staged diff, not the intent

Good examples:
```
harness: add observation envelope with files_changed and process_delta
tests: add adversarial harness component evaluation cases
schemas: add failure-card and mechanism-card templates
```

Bad examples:
```
updates
wip
more work
fix stuff
misc changes
```

### 5. For Mixed or Blocked Candidates

Do not commit blindly. Produce a split plan:

```text
SPLIT_PLAN
- candidate_a:
    files: <list>
    rationale: <why these go together>
    ready: yes | no | why_not
- candidate_b:
    files: <list>
    rationale: <why these go together>
    ready: yes | no | why_not
- blockers:
    - <specific issue preventing commit>
- recommended_order:
    - <which to commit first and why>
```

### 6. Produce the Git Handoff Report

Every run produces a report, even if no commit was made:

```text
GIT_AGENT_REPORT
- ts_utc:
- branch:
- worktree_summary:
- commit_status: committed | commit_ready | split_required | blocked
- commit_candidates:
  - scope:
    files:
    commit_message:
    rationale:
    action_taken:
- deferred_changes:
- blockers:
- evidence_paths:
- next_action:
```

## Guardrails

- Do not wait until the end of a large task to commit. Commit as soon as a
  logical slice is complete.
- Do not mix unrelated changes into the same commit.
- Never commit source-mirror churn (vendored codebase copies) unless that
  mirror was intentionally modified as part of the current work.
- If the worktree contains work from multiple owners or ambiguous intent, stop
  and write a split plan instead of committing blindly.
- The diff is the source of truth. Rewrite a suggested commit message if the
  files or intent have changed since the message was drafted.

## Sources

- `workflows/prompts/git-commit-agent.md` — the full git commit agent role spec,
  including the complete `GIT_AGENT_REPORT` output contract and commit message
  discipline
