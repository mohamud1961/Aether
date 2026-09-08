# Known limitations

Aether is a working research runtime with a green public qualification surface. It is **not** presented as a finished benchmark winner, a general safety solution, or a fully proven agent architecture.

This ledger records the limitations that materially constrain current claims.

## 1. Held-out performance is not yet competitive

The sealed H10 campaign produced **3 passes across 8 validly evaluated rows**.

Its public verdict is:

- runtime mechanical integrity: **ACCEPTED**;
- benchmark competitiveness: **NOT DEMONSTRATED**;
- performance: **NOT COMPETITIVE ON H10 SAMPLE**.

The three-month research programme exists to determine whether measured runtime changes can improve that relationship under matched conditions.

## 2. The strongest selected case is not representative aggregate evidence

The public `configure-git-webserver` Luna + Aether run received official reward **1.0**.

It is deliberately labelled **selected**. It is useful for capability/failure-attribution analysis because Aether's internal completion review still blocked despite the externally passing task-visible result.

It must not be read as representative Aether benchmark performance.

## 3. The Terra + Codex per-task comparator receipt is still pending

Terminal-Bench's official public submission independently verifies the GPT-5.6 Terra max + Codex 0.144.1 configuration and its 445-trial aggregate.

The exact public per-task receipt proving `configure-git-webserver = 0.00` has not yet been attached to this repository.

Therefore the website/repository wording remains **reported 0.00**, and the comparison is a motivating signal rather than a causal A/B.

## 4. Full raw trajectories are not all public

Aether's current Harbor runtime writes:

- `trajectory.json` — ATIF v1.7 trajectory;
- `aether_run_record.json` — complete JSON-serializable run record;
- `aether_x0_observability.json` — deterministic observability summary bound to the exact run-record SHA-256.

However, complete historical/internal traces can include provider details, host identifiers, held-out benchmark material or other content that requires publication review.

The current public release therefore exposes sealed machine-readable records, selected result receipts, hashes/run identifiers and narrative trace summaries where safe. It does **not** pretend a summary is a raw trace.

See [`EVIDENCE_PIPELINE.md`](EVIDENCE_PIPELINE.md) and [`../evidence/MANIFEST.json`](../evidence/MANIFEST.json).

## 5. Public qualification is provider-free

The GitHub Actions qualification proves current source can be installed, imported and deterministically checked on a clean runner.

It intentionally does **not** call a model provider. Therefore it does not prove live provider availability, model behaviour, benchmark-environment reliability or live-agent task performance.

Those remain empirical live-run questions.

## 6. Most Python dependencies are not fully frozen transitively

Harbor integration is exactly pinned to `0.20.0`, and key production identities are hashed/locked.

The Python package does not currently ship a complete transitive environment lock for every ordinary dependency.

To preserve the exact environment behind each public green run, CI records and uploads:

- Python version;
- pip version;
- `pip freeze`;
- commit SHA and runner identity.

This makes the qualification environment inspectable without pretending the package has a stronger dependency-freeze policy than it currently does.

## 7. Licence scope is deliberately limited

The public Aether runtime and deliberately selected project-owned documentation
are released under the project-owned MIT notice at the repository root. The
static funding-site candidate under `website/public/` carries its own site
licence and third-party notice.

These notices do not relicense dependencies, copied or translated third-party
source, benchmark fixtures, generated evidence, private research material,
linked external content, or other files whose provenance has not been checked.

See [`docs/provenance/third_party_notices.md`](provenance/third_party_notices.md)
for the current exception boundary. Any future slice that deliberately
publishes third-party source must add its exact source, licence and attribution
evidence before publication.

This is a legal/publication boundary, not a runtime-performance limitation.

## 8. Current evidence cannot establish the long-term thesis by itself

The central thesis is:

> **better model → better agent**

The existing evidence is enough to motivate a controlled experiment. It is not enough to prove that Aether makes model improvements translate monotonically into agent improvements.

That requires the proposed matched programme:

- same underlying model;
- same task/environment;
- comparable budgets;
- repeated trials fixed before evaluation;
- independent outcome authority;
- negative results published.

## Interpretation rule

These limitations are part of the research case, not exceptions to it.

Aether is fundable because enough real implementation and evidence now exist to make the central question testable—and because the project is designed to publish an informative negative answer if the thesis fails.
