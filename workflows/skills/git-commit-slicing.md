# Git commit slicing

Use this to turn completed, coherent slices of work into intentional commits, especially across a multi-worker build.

## Governing question

> What is the smallest coherent commit that can be made from the current worktree?

Smallest coherent means: one logical change, an accurate message, no unrelated files, and no history rewriting. A commit that dumps a day's work is not coherent. A commit that mixes three unrelated changes is not coherent.

## Do not use for

- Interactive rebase or history rewriting (never by default).
- Force pushes (never without explicit instruction).
- Work still marked partial or blocked in its handoff.

## Workflow

1. **Inspect.** Run `git status --short`, `git diff --stat`, `git diff --cached`, and `git diff`. Read the handoffs or ledger entries for each change's intent.
2. **Cluster files by intent.** Tests go with the code they test. Schema or config goes with the feature it enables. Substantial docs can go with their feature or stand alone.
3. **Classify each candidate:**
   - `committed`: already in history.
   - `commit_ready`: coherent, complete, safe to commit.
   - `split_required`: must be separated first.
   - `blocked`: unclear intent, partial implementation, or mixed ownership.
4. **Commit ready candidates.** Stage only the slice's files, check the staged diff, then commit.
5. **Split mixed candidates.** Do not commit blindly. Write a split plan: each candidate's files, rationale, and readiness, plus the blockers and the order.
6. **Report.** Every run produces a report, even when nothing is committed: branch, commit status per candidate, deferred changes, blockers, evidence paths, and the next action.

## Commit messages

- Imperative mood: "add", "fix", "repair", "remove".
- Specific: `harness: add observation envelope with files_changed` not `updates`.
- Describes the staged diff, not the intent.
- If the slice is not ready, use `HOLD - <reason>` so it can be split or deferred later.
- If there are no tracked changes, use `NONE - no tracked file changes`.

Bad subjects: `updates`, `wip`, `more work`, `fix stuff`, `misc changes`.

## Guardrails

- Do not commit a slice that a handoff marks partial or blocked.
- Do not bundle a repair with unrelated cleanup.
- Do not edit a worktree that another agent is actively using. Check first.
