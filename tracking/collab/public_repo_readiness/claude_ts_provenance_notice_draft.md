# Claude TS Provenance Notice

Date: `2026-06-16`

## Current Evidence

- Source tree inspected:
  - `research/sources/codebases/quarantine/claude-code_ts_release/README.md`
- Local git metadata:
  - `.git/config` remote origin is `https://github.com/yasasbanukaofficial/claude-code.git`
- README evidence says:
  - the local quarantined README contains an MIT placeholder claim;
  - it says copies must include the original copyright and license notice;
  - it says the full license text should appear in a root `LICENSE` file.

## Verified Upstream Evidence

- Official package metadata for `@anthropic-ai/claude-code` points at the
  upstream repository `https://github.com/anthropics/claude-code`.
- The official repository root includes `LICENSE.md`.
- The official repository root does **not** include a standalone `NOTICE`
  file.
- The upstream `LICENSE.md` text is:

  > © Anthropic PBC. All rights reserved. Use is subject to Anthropic's
  > Commercial Terms of Service.

## Publication Status

The earlier MIT placeholder is superseded by the verified Anthropic license
pointer above.

This source-specific publication gap is now **resolved** for notice purposes as
long as published docs use the verified upstream text and do not reintroduce an
MIT placeholder claim.

## Notice Block For Internal Tracking

```text
Third-party source provenance (draft)

This repository contains Python ports/adaptations derived from source files in:
research/sources/codebases/quarantine/claude-code_ts_release/

Available local evidence:
- README.md in that source tree is a local placeholder and is not authoritative
  for upstream licensing.

Verified upstream evidence:
- official repository: https://github.com/anthropics/claude-code
- root license file: LICENSE.md
- license text: © Anthropic PBC. All rights reserved. Use is subject to
  Anthropic's Commercial Terms of Service.
- no standalone NOTICE file was found in the official repository root.

Publication rule:
- Publish the verified upstream text above, and do not restate the local README
  as if it were the upstream license.
```

## Required Follow-Up Before Public Release

1. Keep `docs/provenance/third_party_notices.md` as the public-facing notice
   source of truth.
2. Re-check any additional quarantined source trees independently before
   reusing this notice.
3. Confirm no later packaging step reintroduces the MIT placeholder.
