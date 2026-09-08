# Evidence pipeline

Aether is designed so a run leaves evidence that can be inspected independently of the model's final narrative.

This document describes the **current production evidence path**. It is implementation-backed; the canonical code lives in [`../aether/harbor_runtime.py`](../aether/harbor_runtime.py), [`../aether/atif_export.py`](../aether/atif_export.py), [`../aether/postmerge_observability.py`](../aether/postmerge_observability.py), and the ledger/receipt modules under [`../aether/`](../aether/).

## Runtime evidence custody

For a canonical Harbor run, Aether first discovers the real workspace from Harbor-authoritative probes. It then runs the selected model/runtime treatment against that environment.

Before the run record leaves the Harbor adapter, the current runtime materializes three evidence artifacts under Harbor's agent-log custody.

### 1. `trajectory.json`

An **ATIF v1.7** trajectory built from the instruction and exact Aether run record.

This is the interoperable trajectory surface.

### 2. `aether_run_record.json`

The complete JSON-serializable Aether run record.

The adapter writes the bytes, computes their **SHA-256**, and stores that hash back into the run metadata.

### 3. `aether_x0_observability.json`

A deterministic observability summary built from:

- model-call telemetry;
- model-interface captures;
- receipt records.

Its `source_run` block records the exact path and SHA-256 of `aether_run_record.json`, plus runtime identity, status and step.

That means the X0 summary is not a free-floating retrospective narrative; it is bound to the persisted run record it summarizes.

## Runtime identity

The Harbor adapter records a runtime identity including, where available:

- task ID and authority;
- run ID and authority;
- source commit;
- runtime-manifest SHA-256;
- campaign ID;
- task-closure SHA-256;
- package-closure SHA-256;
- Harbor context ID;
- environment digest;
- immutable model-profile manifest + SHA-256;
- effective run budgets.

This lets later forensics distinguish *what code/model/environment actually ran* from what a human remembers running.

## Cancellation and grading race

Harbor owns benchmark lifecycle and official grading.

If the outer coroutine is cancelled, Aether revokes authority through a shared cancellation event and keeps shielding/waiting until the synchronous worker has actually quiesced.

The purpose is narrow but important:

> grading should not race a still-running agent thread that can mutate the task world after timeout/cancellation.

This is part of evidence integrity, not merely timeout handling.

## External evaluation remains external

Aether records its own execution/review evidence, but official benchmark evaluation remains outside the model's context and outside Aether's strategic control.

A run is not called successful merely because its internal trace looks coherent. External task-visible evaluation remains the performance authority.

## Public evidence pipeline

Internal evidence custody and public evidence publication are separate stages.

```text
live run
  ↓
ATIF trajectory + complete run record + receipts/X0
  ↓
hashes / provenance / sealed campaign record
  ↓
publication review + redaction
  ↓
public raw trace OR public receipt/projection/summary
  ↓
evidence/MANIFEST.json labels exactly what was published
```

A raw internal trace may contain information that should not be promoted blindly: provider metadata, host identifiers, held-out task material, credentials-adjacent context or irrelevant private workspace state.

Therefore the public repository does **not** equate "internally recorded" with "safe to publish."

## Public evidence types

The public evidence layer distinguishes four forms:

1. **Raw trajectory** — event/action/model evidence from the original run after publication review.
2. **Sealed machine-readable record** — authoritative result/campaign record with provenance and hashes.
3. **Derived projection** — a convenience JSON extracted from a sealed record and labelled as derived.
4. **Narrative summary** — human-readable explanation, never presented as a raw trace.

See [`../evidence/MANIFEST.json`](../evidence/MANIFEST.json).

## Current public gap

The strongest selected historical Luna/Aether case preserves an original run ID and SHA-256 hashes for its trajectory, run record, CTRF and reward, but the full 25-file historical bundle is not yet in this curated public release.

That gap is explicit. The repository will not reconstruct a synthetic trajectory and call it raw evidence.

The next correct publication step is to retrieve the original preserved bundle, run a separate redaction/publication review, verify the published artifact hashes/provenance, and promote only the safe subset.

## Why this matters for the research programme

The proposed matched experiment needs more than final benchmark scores.

For each run, the evidence pipeline is intended to let us separate:

- model reasoning/continuation failure;
- malformed model/tool protocol;
- runtime execution failure;
- permission/boundary rejection;
- recovery behaviour;
- provider/infrastructure invalidity;
- completion-review disagreement;
- external task failure.

That attribution layer is what turns a benchmark board into research about **why a capable model became a capable—or incapable—agent**.
