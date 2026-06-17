# License Notice Recovery Handoff

Source thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`

## Final Status

`complete`

I recovered and verified the upstream licensing evidence for the quarantined
TS-derived source used by the direct TS-to-Python port slices, updated the
public provenance notice, and marked the specific publication gap as resolved
for this source tree.

## Objective Completed

- Recover the upstream LICENSE / notice text for the quarantined TS-derived
  source.
- Distinguish local quarantine evidence from verified upstream evidence.
- Update public-safe notice and gap-list docs.
- Validate the changed docs with cheap path and formatting checks.
- Persist a raw ledger handoff for historian review.

## Scope Actually Completed

- Inspected the quarantined source tree metadata without mutating it.
- Verified the embedded git remote and local README text.
- Identified the official upstream source family through npm metadata and the
  official Anthropic GitHub repository.
- Confirmed the upstream root license text and the absence of a standalone
  upstream `NOTICE` file.
- Updated the publication gap list and provenance draft to stop repeating the
  local MIT placeholder as if it were authoritative.

## Evidence Inspected

### Local evidence

- `research/sources/codebases/quarantine/claude-code_ts_release/README.md`
- `research/sources/codebases/quarantine/claude-code_ts_release/.git/config`
- `research/sources/codebases/quarantine/claude-code_ts_release/.git/HEAD`
- `research/sources/codebases/quarantine/claude-code_ts_release/.git/logs/HEAD`
- `git -C research/sources/codebases/quarantine/claude-code_ts_release ls-tree`

### Verified upstream evidence

Retrieved `2026-06-16`.

- npm registry metadata:
  - `https://registry.npmjs.org/@anthropic-ai%2fclaude-code/2.1.0`
- npm package tarball:
  - `https://registry.npmjs.org/@anthropic-ai/claude-code/-/claude-code-2.1.0.tgz`
- Official repository contents:
  - `https://api.github.com/repos/anthropics/claude-code/contents?ref=main`
- Official root license file:
  - `https://raw.githubusercontent.com/anthropics/claude-code/main/LICENSE.md`
- Official root notice check:
  - `https://raw.githubusercontent.com/anthropics/claude-code/main/NOTICE`

### Verified upstream text

The upstream `LICENSE.md` says:

> © Anthropic PBC. All rights reserved. Use is subject to Anthropic's
> Commercial Terms of Service.

The official repository does not have a standalone root `NOTICE` file.

## Files Changed

- `docs/provenance/third_party_notices.md`
- `docs/publication/publication_gap_list.md`
- `tracking/collab/public_repo_readiness/claude_ts_provenance_notice_draft.md`

## Requirement-by-Requirement Disposition

1. Inspect the local quarantined source tree and metadata thoroughly.
   - `done`
   - The quarantine tree was inspected read-only. Local metadata was traced to
     `https://github.com/yasasbanukaofficial/claude-code.git`.
2. If local evidence is insufficient, use network only to fetch primary-source
   licensing evidence from the exact upstream repository/source identified by
   local metadata.
   - `done`
   - Primary-source evidence was fetched from the official Anthropic repo and
     npm registry.
3. Decide whether publication can be unblocked.
   - `done`
   - The specific gap is resolved for this source tree, with the caveat that
     the upstream license is Anthropic commercial-terms text, not MIT.
4. Preserve source-derived compatibility names and provenance markers.
   - `done`
   - The `claude_ts_*` handoff naming was preserved.
5. Run validation.
   - `done`
   - Path existence checks, `git diff --check`, and
     `python3 tools/aether2_genericity_check.py` all passed.
6. Review gate: adversarial_only.
   - `done`
   - Manual adversarial review completed from legal/provenance, public-hiring-
     reviewer, and maintainer angles.
7. Persist a RAW_LEDGER_UPDATE if material.
   - `done`
   - Ledger update written to
     `tracking/ledger/inbox/2026-06-16/005520_worker-16_recover-and-verify-upstream-license-notice-text-for-claude-code-ts-release-and-update-public-ready-notice-docs_2f02a8f0c3.md`
8. Write a full handoff to this file.
   - `done`
9. Hand the result back to the originating orchestrator thread.
   - `done`

## Validation

- Path existence check:
  - passed for `docs/provenance/third_party_notices.md`
  - passed for `docs/publication/publication_gap_list.md`
  - passed for `tracking/collab/public_repo_readiness/claude_ts_provenance_notice_draft.md`
- Formatting check:
  - `git diff --check -- docs/provenance/third_party_notices.md docs/publication/publication_gap_list.md tracking/collab/public_repo_readiness/claude_ts_provenance_notice_draft.md`
  - passed
- Genericity check:
  - `python3 tools/aether2_genericity_check.py`
  - passed

## Adversarial Review

### Legal / provenance perspective

- Finding: the local quarantined README claims MIT, but that claim is not
  authoritative.
  - Disposition: accepted.
  - Evidence: official upstream repo `LICENSE.md` and npm metadata point to
    Anthropic commercial-terms licensing, not MIT.
- Finding: no standalone upstream `NOTICE` file exists.
  - Disposition: accepted.
  - Evidence: the official root `NOTICE` URL returned `404 Not Found`.

### Public-hiring-reviewer perspective

- Finding: the public docs must not imply broader redistribution rights than
  the upstream text actually provides.
  - Disposition: accepted.
  - Evidence: the new notice doc explicitly removes the MIT framing and uses the
    verified upstream pointer instead.

### Maintainer perspective

- Finding: the provenance docs must preserve the `claude_ts_*` markers and not
  rename them away.
  - Disposition: accepted.
  - Evidence: filenames and links were left intact.

## Publication Blocker Status

Resolved for this source tree.

The remaining risk is not that the upstream evidence is missing, but that a
later packaging step or another doc edit could reintroduce the local MIT
placeholder. The current notice doc is the source of truth for this tree.

## Unresolved Risks / Next Action

- Re-check any additional quarantined source trees independently before reusing
  this notice pattern.
- If another source tree is added later, verify its own upstream license text
  instead of inheriting this one by analogy.

## External State

- No VMs, containers, eval runs, or long-running servers were started.
- No external state remains active.

## RAW_LEDGER_UPDATE

Persisted raw ledger handoff:

- `tracking/ledger/inbox/2026-06-16/005520_worker-16_recover-and-verify-upstream-license-notice-text-for-claude-code-ts-release-and-update-public-ready-notice-docs_2f02a8f0c3.md`
