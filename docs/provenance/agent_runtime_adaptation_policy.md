# Agent Runtime Adaptation Policy

Status: draft public-safe provenance note for source-adaptation planning.

## Purpose

HarnessEng may study external agent runtimes and local research copies in this
repository to identify useful capability patterns. Public runtime code must
remain a Python-native Aether design with repo-local provenance, explicit eval
coverage, and no undisclosed source translation.

## Current Local Evidence

Local research copies may exist outside the public artifact set. They are
private inputs for design analysis, not public repository content and not
authority for direct reuse. The public repo should carry only provenance
policy, verified notice text, and independently implemented HarnessEng code.

Earlier planning found that at least one local research copy lacked complete
repo-local license and notice metadata. That is enough to block direct code
reuse until the source, license, notice obligations, and exact reused surface
are verified and recorded.

## Policy

1. No code may be copied, translated, or mechanically ported from external
   research copies into `harness.aether2` without a repo-local provenance
   bundle that includes the exact upstream source, license, and any required
   attribution or notice obligations.
2. If a local research copy lacks a discoverable `LICENSE` or `NOTICE` file in
   the checkout used for implementation planning, direct code reuse is blocked
   in this repository until that gap is repaired and recorded.
3. Concept-level reimplementation is allowed when it is:
   - expressed as a new Python design owned by HarnessEng;
   - justified by a custom eval or sentinel first;
   - validated in Aether's own runtime and trace model;
   - documented as inspiration rather than affiliation or equivalence.
4. Public docs and code must not claim external affiliation, external product
   branding, or behavioral parity with any external product.
5. Public portfolio value should come from owned interfaces, eval evidence, and
   engineering discipline, not from reproducing a leaked or mirrored codebase.

## Allowed Inputs For Design Work

- capability inventories;
- architecture notes describing broad subsystem boundaries;
- behavioral observations from local use;
- independent public documentation or standards when available;
- repo-local eval evidence showing why Aether needs a capability.

## Disallowed Inputs For Direct Implementation

- line-by-line translation from external TypeScript or binary artifacts;
- copied prompts, private policy text, or provider internals;
- copied UI flows, auth flows, telemetry systems, or branding surfaces;
- external-suite-specific solve logic justified by outside runtime behavior
  alone.

## Approval Bar Before Any Future Reuse

Before any direct reuse question is reopened, add a repo-local provenance record
that names:

- the exact source reference used;
- the exact license evidence;
- any required `NOTICE` or attribution text;
- what code, if any, is being reused versus reimplemented;
- the evals that will guard the new behavior.
