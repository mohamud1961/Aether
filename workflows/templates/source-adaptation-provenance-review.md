# Source Adaptation Provenance Review

Use this when adapting ideas from an external source or source tree while
keeping the public implementation owned, generic, and publication-safe.

## Minimum Record

- exact source or source family used;
- exact source files read, if any;
- exact target files changed;
- what was adapted, reimplemented, or deliberately excluded;
- validation evidence for the new behavior;
- public claims explicitly excluded or qualified.

## Publication Guardrails

- Do not imply affiliation or parity with the source project.
- Do not publish copied or derived work without verified license and notice
  obligations.
- Keep UI, auth, telemetry, branding, and proprietary surfaces out of scope
  unless they are intentionally covered.
- Record missing license or notice text as an open publication gap, not as a
  silent assumption.

## Review Questions

- Is the implementation generic rather than external-suite-shaped?
- Is the provenance trail explicit enough for later publication audit?
- Are simplifications and deferred pieces visible to reviewers?
- Would a maintainer understand what still blocks public release?
