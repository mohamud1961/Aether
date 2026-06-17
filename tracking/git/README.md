# Git Handoffs

This folder stores durable git-agent handoff reports.

Use it for:

- commit candidate clustering
- commit-ready versus blocked status
- proposed commit messages
- split plans for mixed worktrees
- rationale for why a commit was or was not made

Naming convention:

- `tracking/git/<YYYY-MM-DD>__<HHMMSS>__git_agent_handoff.md`

Recommended format:

```text
GIT_AGENT_REPORT
- ts_utc:
- branch:
- worktree_summary:
- commit_status: committed | commit_ready | split_required | blocked
- commit_candidates:
  - scope:
  - files:
  - commit_message:
  - rationale:
  - action_taken:
- deferred_changes:
- blockers:
- evidence_paths:
- next_action:
```
