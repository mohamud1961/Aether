# Tracking

This top-level folder holds durable project tracking surfaces that are operational rather than research-source content.

Layout:

- `tracking/ledger/` - canonical historian ledger, raw handoff inbox, and recorder helper
- `tracking/git/` - git-agent handoff reports and commit-tracking notes
- `tracking/collab/` - structured multi-agent collaboration workspaces, task packets, and synthesis artifacts

Why this exists:

- keeps cross-session tracking separate from the research corpus itself
- keeps git tracking separate from source analysis and raw research artifacts
- gives agents one stable place to persist operational state across sessions

Compatibility:

- `research/ledger` is kept as a compatibility symlink to `tracking/ledger`
- `research/notes/git` is kept as a compatibility symlink to `tracking/git`

New work should use the `tracking/` paths as canonical.
