# Variant Family Seeds Decision

Status: packet instantiated, queued behind `eval_implications`

Opened: 2026-04-02

Artifact

- `variant_family_seeds`

Goal

- Turn accepted Deep Synthesis findings into evidence-backed candidate variant families.

Why this packet exists now

- The owner requested the full Deep Synthesis stage to be concretized, not just the opening artifacts.
- `variant_family_seeds` is the planned final Deep Synthesis artifact and should inherit the whole upstream synthesis chain.

Collaboration mode

- Hybrid:
  - blind-parallel seed proposals
  - pruning critic
  - contradiction review
  - principal synthesis

External-agent call

- Run external agent now: no.
- Reason: this artifact is queued behind `eval_implications`.
- If `eval_implications` is accepted and the owner keeps artifact order unchanged:
  - Run external agent now: yes.
  - Agent: Deep Synthesis `variant_family_seeds` synthesis chain
  - Why now: upstream mechanism, failure, and eval implication handoffs will then exist in structured form.
  - Expected output path: `tracking/collab/stage_02_synthesis/variant_family_seeds/outputs/`

Launch judgment

- This packet is now structurally concrete.
- It now sits inside the compressed `14`-wave Deep Synthesis model and closes in two core waves rather than the older longer wave chain.
- It should not open before `eval_implications` principal synthesis is accepted.
- The required handoff path from `eval_implications` is part of the launch gate.

Next move

- Review `tracking/collab/stage_02_synthesis/variant_family_seeds/brief.md`.
- Keep this packet queued behind `eval_implications`.
