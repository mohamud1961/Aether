# Provenance And Publication Review

Use this skill when adapting, curating, or publishing material that came from
another source tree or from private collaboration history.

The goal is to keep the publication trail explicit without exposing raw private
artifacts or implying stronger claims than the evidence supports.

## Governing Question

> What exactly was sourced, what exactly was adapted, and what exactly remains
> withheld?

## When To Use

Use this skill for:

- direct ports or subsystem adaptations;
- publication-packaging work;
- case-study writing from internal evidence;
- public navigation and evidence-index updates;
- release or provenance review of docs that might overclaim readiness.

## Minimum Record

Track the following:

- exact source tree or source surface used;
- exact source files read;
- exact target files changed;
- what was ported, adapted, reimplemented, or excluded;
- validation evidence for the new public behavior;
- public claims that were explicitly excluded or qualified;
- license or notice obligations that still need verification.

## Publication Guardrails

- Do not imply affiliation or parity with the source project.
- Do not publish copied or derived work without verified license and notice
  obligations.
- Keep UI, auth, telemetry, and proprietary surfaces out of scope unless they
  are intentionally covered.
- Keep raw private trajectories, hidden graders, raw ledgers, and private
  fixtures out of the public layer.
- Treat missing license or notice text as a publication gap, not as a silent
  assumption.

## Review Questions

Ask these before closing the slice:

- Is the implementation generic rather than external-suite-shaped?
- Is the provenance trail explicit enough for later audit?
- Are simplifications and deferred pieces visible to reviewers?
- Would a maintainer understand what still blocks public release?
- Does the public wording stay below the level of proof available?

## Public Output

A good publication review should leave behind:

- a clear provenance summary;
- a list of intentionally withheld material;
- a validation note;
- a conservative claims boundary;
- the next publication gap, if any.

## Companion Template

Use [Source adaptation provenance review](../templates/source-adaptation-provenance-review.md)
for the compact checklist form.
