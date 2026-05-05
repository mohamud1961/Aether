# Deep Synthesis v1 Audit Checklist

Use this as the formal review gate for the first deep-synthesis deliverable.

This checklist is for auditing whether Deep Synthesis v1 is:

- sufficiently grounded
- sufficiently detailed
- structurally complete enough for the next phase
- honest about uncertainty
- actually useful for mechanism mapping, failure taxonomy, variant design, and eval design

This is not a checklist for writing style or surface polish.
It is a checklist for substance, rigor, structure, and usefulness.

## 0. Scope and Phase Discipline

- [ ] Deep Synthesis v1 stays in scope: it synthesizes the evidence base, not final architecture recommendations.
- [ ] It does not prematurely declare a winning harness design.
- [ ] It does not collapse directly into variant selection without first building mechanism and failure structure.
- [ ] It does not blur research synthesis with experiment results.
- [ ] It does not silently rewrite the project goal.
- [ ] It remains aligned to the real target: best general-purpose terminal task-execution harness.
- [ ] It treats the harness as the full non-model execution system, not just workflow or prompting.
- [ ] It keeps anti-benchify discipline intact.
- [ ] It does not quietly narrow the project into only one benchmark or one lab's philosophy.
- [ ] It explicitly marks what belongs to deep synthesis now versus what belongs to later experiment phases.

## 1. Source-of-Truth Discipline

- [ ] The synthesis is clearly grounded in the approved evidence pool.
- [ ] It identifies what corpus/manifests were actually used.
- [ ] It does not silently rely on stale seed docs as evidence.
- [ ] It does not use unsafe or unapproved corpus partitions without saying so.
- [ ] It distinguishes between:
  - formal sources
  - provider/lab docs
  - open-source repos
  - postmortems/issues
  - trajectories/traces
  - informal artifacts
- [ ] It preserves provenance throughout.
- [ ] Every major claim can be traced back to concrete source families or artifacts.
- [ ] It does not let repeated informal opinions masquerade as evidence depth.
- [ ] It does not over-index on the most normalized source family just because it is easier to work with.
- [ ] It makes explicit where evidence is direct, partial, inferred, or weak.

## 2. Mechanism Map Quality

### Existence and structure

- [ ] A real mechanism map artifact exists.
- [ ] Mechanisms are not just listed loosely; they are structured into families and subfamilies.
- [ ] The mechanism map covers the full harness, not just the most fashionable buckets.
- [ ] The mechanism map is detailed enough to support later variant design.
- [ ] Mechanisms are described in operational terms, not vague abstractions.

### Per-mechanism rigor

For each meaningful mechanism or mechanism family:

- [ ] It states what the mechanism is.
- [ ] It states what problem the mechanism is supposed to solve.
- [ ] It states where in the harness it lives.
- [ ] It states how it works at an operational level.
- [ ] It states what evidence supports it.
- [ ] It states what evidence complicates or contradicts it.
- [ ] It states what task regime the evidence comes from.
- [ ] It states what failure modes the mechanism is supposed to reduce.
- [ ] It states likely tradeoffs or downsides.
- [ ] It states likely interactions with other harness parts.
- [ ] It gives a confidence level or uncertainty note.
- [ ] It does not overclaim beyond the evidence.

### Coverage

- [ ] Mechanisms are covered for:
  - policy/program layer
  - workflow/architecture
  - tool gateway
  - execution control
  - context
  - state
  - artifacts/workspace
  - memory
  - verification/completion
  - recovery
  - observability
  - sandboxing/environment
  - eval-related mechanisms
- [ ] Interaction-sensitive mechanisms are not ignored.
- [ ] Simple mechanisms are included, not just advanced ones.
- [ ] Complex mechanisms are decomposed instead of treated as monoliths.

## 3. Failure Taxonomy Quality

### Existence and structure

- [ ] A real failure taxonomy artifact exists.
- [ ] It is not just a list of anecdotes.
- [ ] Failures are grouped into clear classes/subclasses.
- [ ] The taxonomy is grounded in real trajectories/issues/postmortems, not just intuition.
- [ ] It distinguishes failure symptoms from failure causes.

### Per-failure rigor

For each failure class:

- [ ] It defines the failure clearly.
- [ ] It describes how the failure manifests in practice.
- [ ] It gives concrete examples or source families where it appeared.
- [ ] It identifies whether it is likely harness, model, environment, or interaction-driven.
- [ ] It notes uncertainty where attribution is unclear.
- [ ] It identifies likely upstream causes.
- [ ] It identifies downstream effects.
- [ ] It identifies which harness mechanisms might prevent, mitigate, or detect it.
- [ ] It notes whether the failure is common, severe, subtle, or benchmark-specific.
- [ ] It differentiates between recoverable and terminal failures.

### Coverage

- [ ] The taxonomy includes failures around:
  - false completion
  - tool misuse
  - bad tool output handling
  - context flooding
  - context starvation
  - stale context
  - bad retrieval
  - state drift
  - artifact/workspace sloppiness
  - bad memory writes
  - bad memory retrieval
  - missing verification
  - bad rollback/recovery
  - workflow coordination failure
  - sandbox/environment mismatch
  - observability gaps
- [ ] It covers both local component failures and cross-component failures.
- [ ] It includes failures visible in traces, not just reported in papers.
- [ ] It does not treat all failures as equal if some are clearly higher leverage than others.

## 4. Mechanism-to-Failure Mapping

- [ ] The synthesis does more than separately list mechanisms and failures.
- [ ] It explicitly maps failure classes to candidate mechanisms.
- [ ] It shows where a mechanism is supposed to help a failure.
- [ ] It shows where a mechanism may introduce new failure modes.
- [ ] It distinguishes:
  - preventive mechanisms
  - detection mechanisms
  - containment mechanisms
  - recovery mechanisms
- [ ] It flags cases where there is no convincing mechanism yet.
- [ ] It flags cases where multiple mechanisms seem to address the same failure.
- [ ] It flags cases where the same mechanism may help in one regime and hurt in another.
- [ ] It does not pretend causal certainty where the mapping is only suggestive.

## 5. Bucket-by-Bucket Deep Coverage

For each bucket, check that the synthesis is more than surface-level.

### Policy / Program Layer

- [ ] It covers doctrine, invariants, stop rules, escalation rules, and structured task rules.
- [ ] It distinguishes between instruction content and control logic.
- [ ] It identifies where policy appears to matter operationally.
- [ ] It identifies where policy may be compensating for missing machinery elsewhere.

### Workflow / Architecture

- [ ] It covers major workflow families.
- [ ] It distinguishes workflow patterns from the underlying mechanisms they depend on.
- [ ] It avoids romanticizing multi-agent designs.
- [ ] It identifies where workflow complexity is justified versus decorative.
- [ ] It includes coordination overhead and failure propagation.

### Tool Gateway

- [ ] It covers more than “tool use.”
- [ ] It includes schemas, permissions, retries, idempotency, error surfaces, post-tool handling, and read/write discipline.
- [ ] It captures how tool results are handled after execution.
- [ ] It distinguishes contract quality from model tool-selection skill.

### Execution Control

- [ ] It covers loop structure, replanning, stopping, loop breakers, budget control, and interruptibility.
- [ ] It distinguishes search behavior from exploitation behavior.
- [ ] It identifies when execution policy affects outcomes more than architecture labels do.

### Context

- [ ] It decomposes context into subfamilies instead of treating it as one thing.
- [ ] It covers:
  - what gets persisted
  - how it is organized
  - how it is retrieved
  - how it is injected
  - how overflow is handled
- [ ] It addresses signal/noise and decision usefulness, not just retrieval relevance.
- [ ] It captures when simpler context designs may outperform more elaborate ones.

### State

- [ ] It distinguishes state from memory and from context.
- [ ] It covers authoritative state vs derived state.
- [ ] It covers state drift, manifests, checkpoints, replayability, and resumability.
- [ ] It captures whether state is explicit, implicit, or reconstructed.

### Artifacts / Workspace

- [ ] It covers scratch files, progress files, handoff docs, receipts, TODO stores, test/result artifacts, and cleanliness rules.
- [ ] It treats workspace discipline as a first-class harness concern.
- [ ] It connects artifact discipline to long-horizon continuity and recovery.

### Memory

- [ ] It distinguishes memory from state and context persistence.
- [ ] It covers write policy, retrieval policy, invalidation, contamination, and cross-session use.
- [ ] It does not assume memory is good by default.
- [ ] It identifies when memory is helping versus compensating for weak context/state design.

### Verification / Completion

- [ ] It covers verifier gating, tests, external oracles, completion contracts, and false-completion prevention.
- [ ] It treats completion doctrine as high-leverage.
- [ ] It distinguishes self-report from evidence-backed completion.

### Recovery / Fault Tolerance

- [ ] It covers retry, rollback, re-anchor, restart, state repair, degraded mode, and environment reset.
- [ ] It addresses both detection and action.
- [ ] It captures when recovery policy is essential rather than optional.

### Observability / Audit

- [ ] It covers traces, receipts, model I/O capture, replay, diagnosis support, and auditability.
- [ ] It treats observability as both a harness concern and a scientific concern.
- [ ] It notes where weak observability blocks later experimentation.

### Sandbox / Execution Environment

- [ ] It covers environment policy, persistence, reset semantics, permissions, network policy, toolchain preload, and browser coupling where relevant.
- [ ] It distinguishes environment substrate from sandbox policy.
- [ ] It recognizes environment as a harness concern, not just infrastructure background noise.

### Evals / Benchmarking

- [ ] It synthesizes eval-relevant findings rather than just listing benchmark names.
- [ ] It identifies what existing public evals cover and what they miss.
- [ ] It highlights where custom evals will be necessary.
- [ ] It captures anti-overfit and anti-benchify implications.

## 6. Interaction Analysis

- [ ] There is a real interaction map or equivalent.
- [ ] Interaction is not left as a vague note.
- [ ] The synthesis explicitly covers important cross-bucket interactions.
- [ ] It identifies likely high-leverage interaction pairs or triples.
- [ ] It identifies where strong local mechanisms may combine badly.
- [ ] It identifies where a mechanism cannot be judged in isolation.
- [ ] It captures interaction examples like:
  - tools × context
  - context × verification
  - state × recovery
  - workflow × context partitioning
  - memory × context
  - sandbox × tooling
  - policy × verification
- [ ] It flags interaction gaps where the current corpus is weak.
- [ ] It does not pretend the harness is modular in a way the evidence does not support.

## 7. Contradiction Handling

- [ ] A contradiction register exists, or an equivalent explicit contradiction treatment exists.
- [ ] Contradictions are not hidden or smoothed away.
- [ ] The synthesis explicitly identifies where sources disagree.
- [ ] It distinguishes:
  - source-intent vs observed behavior
  - provider claims vs OSS practice
  - formal evidence vs informal claims
  - one trajectory family vs another
  - one task regime vs another
- [ ] It uses contradictions to create open questions rather than bury them.
- [ ] It identifies where disagreement is likely due to:
  - different definitions
  - different task regimes
  - different model families
  - different harness scopes
  - different cost/latency assumptions
- [ ] It does not force false consensus.

## 8. Evidence Weighting and Confidence

- [ ] The synthesis clearly distinguishes strong evidence from weak evidence.
- [ ] It does not let quantity of sources outweigh quality of sources.
- [ ] It does not let informal artifacts dominate conclusions.
- [ ] It is explicit about which claims are:
  - strongly supported
  - moderately supported
  - tentative
  - speculative
- [ ] Confidence is tied to provenance and evidence quality, not just repetition.
- [ ] It marks where evidence is family-local and not safely generalizable.
- [ ] It avoids converting repeated hearsay into mechanism truth.

## 9. Trace and Trajectory Integration

- [ ] Real traces are used substantively, not just mentioned.
- [ ] The synthesis uses trajectories to identify concrete failure patterns.
- [ ] The synthesis uses trajectories to infer actual workflow and harness behavior.
- [ ] It does not treat trajectories as proof of intent unless corroborated.
- [ ] It distinguishes between:
  - what the system appears to do
  - what the repo code implements
  - what authors/providers claim it does
- [ ] BigAI does not dominate uncritically.
- [ ] Deepagents and terminus-kira are not ignored just because they are less normalized.
- [ ] Uneven normalization is explicitly accounted for in confidence.
- [ ] Raw trajectory evidence is linked back to mechanism and failure artifacts where possible.

## 10. Simplicity vs Complexity Discipline

- [ ] The synthesis does not systematically favor complex mechanisms.
- [ ] Simpler mechanisms are treated as first-class contenders.
- [ ] It explicitly notes where complexity may be unjustified.
- [ ] It identifies where complexity is bundled and hard to attribute.
- [ ] It captures cases where simple designs may outperform richer ones.
- [ ] It does not let prestige architecture bias the synthesis.
- [ ] It identifies where complexity should later be tested via ablation.
- [ ] It treats “minimal sufficient mechanism” as an important lens.

## 11. Open Questions and Unresolved Areas

- [ ] There is an explicit open-questions register or equivalent.
- [ ] Open questions are concrete and decision-relevant.
- [ ] They arise from actual evidence gaps or contradictions.
- [ ] They are not just generic “more research needed” filler.
- [ ] They clearly identify what is still unknown.
- [ ] They identify where later evals must decide rather than synthesis.
- [ ] They identify where a mechanism remains underspecified.
- [ ] They identify where coverage is still weak by bucket or interaction.

## 12. Transition Readiness for Variant Design

- [ ] The synthesis is rich enough to produce provisional variant families.
- [ ] It identifies actual swappable mechanism families.
- [ ] It does not jump straight to full architecture contenders.
- [ ] It identifies where atomic variants are possible.
- [ ] It identifies where combo variants are more appropriate.
- [ ] It identifies candidate simple baselines.
- [ ] It identifies likely complexity traps in variant design.
- [ ] It gives enough structure that later variant cards can be defined without guesswork.

## 13. Transition Readiness for Eval Design

- [ ] The synthesis is rich enough to inform eval architecture.
- [ ] It identifies which failure classes are most important to discriminate.
- [ ] It identifies which mechanisms need atomic evals.
- [ ] It identifies which mechanisms need dependent-part evals.
- [ ] It identifies which interactions will require interaction evals.
- [ ] It identifies which public evals may cover certain buckets.
- [ ] It identifies what must be custom-built.
- [ ] It identifies where the future eval suite must be especially careful to avoid bias or complexity contamination.

## 14. Structural Quality of the Synthesis Artifacts

- [ ] The outputs are not just long prose.
- [ ] The outputs are structured enough to be reused downstream.
- [ ] Mechanism/failure/interaction/open-question artifacts are separable and navigable.
- [ ] The artifacts are audit-friendly.
- [ ] The structure is consistent across buckets.
- [ ] It is possible to compare buckets without confusion.
- [ ] It is possible to trace from summary statements back to source-backed detail.
- [ ] The artifact set feels like research infrastructure, not just notes.

## 15. Honesty and Epistemic Discipline

- [ ] The synthesis is honest about what it does not know.
- [ ] It does not use impressive language to hide weak grounding.
- [ ] It clearly marks inference versus direct source-backed observation.
- [ ] It clearly marks where trace interpretation is speculative.
- [ ] It does not oversell partial evidence.
- [ ] It does not treat normalized structure as solved truth.
- [ ] It preserves ambiguity where ambiguity is real.
- [ ] It is more interested in getting the mechanism structure right than sounding complete.

## 16. Review Gate Questions

Use these as the final gate questions after reading Deep Synthesis v1.

- [ ] Can I clearly see what the major mechanism families are?
- [ ] Can I clearly see what the major failure classes are?
- [ ] Can I see how mechanisms and failures connect?
- [ ] Can I see which buckets are genuinely strong versus still thin?
- [ ] Can I see where the corpus disagrees with itself?
- [ ] Can I see where traces materially changed the understanding?
- [ ] Can I see where simple designs might be enough?
- [ ] Can I see the likely high-leverage variant families?
- [ ] Can I see the likely eval requirements emerging from the synthesis?
- [ ] Can I trust this synthesis enough to use it as the backbone for the next phase?

If several of those are `no`, Deep Synthesis v1 is not strong enough yet.

## Required return shape from the adjudicator

Ask the adjudicator to return:

### A. Pass / Fail / Partial by section

For each major section above:

- `pass`
- `partial`
- `fail`

### B. Concrete evidence

For every `pass`, require:

- file paths
- section names
- artifact names
- brief proof

### C. Gap list

For every `partial` or `fail`, require:

- exactly what is missing
- whether it is structural or just incomplete detail
- how they plan to fix it

### D. Confidence note

Ask:

- what parts of the synthesis are strongest?
- what parts are still fragile?
- what parts may be over-influenced by one source family?

### E. Readiness verdict

Force one of:

- not ready for variant design
- ready for provisional variant families only
- ready for provisional variants and eval architecture inputs
- ready for next stage with minor cleanup only

## Additional instruction

Do not mark something `pass` because there is a mention of it somewhere.
Mark it `pass` only if it is synthesized, structured, evidence-grounded, and usable for downstream work.
