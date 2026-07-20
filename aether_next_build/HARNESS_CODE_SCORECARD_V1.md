# Aether-Next Harness Code Scorecard v1

Certification version: 1.0
Status at freeze: NOT READY

## Certification meaning

100/100 means every invariant in this frozen version is implemented and closed
through its production owner with positive, adversarial-negative, integration,
and required VM evidence. It does not mean every probabilistic model solves
every task.

A newly discovered invariant creates a new scorecard version and suspends
current readiness until the new version is certified. It does not make earlier
evidence dishonest.

Any open critical invariant blocks promotion regardless of arithmetic total.

## Scoring

| ID | Area | Points | Promotion blocker | Closure condition |
|---|---|---:|---|---|
| A1 | Architectural purity | 5 | yes | Trusted production code contains no task-family semantic strategy and exposes one fixed generic tool surface. |
| A2 | Canonical production path | 5 | yes | One kernel, Architect IR/compiler, Solver protocol, ledger, context compiler, Verifier protocol, runner, evidence finaliser, and completion path are identified; alternatives are removed or quarantined. |
| P1 | Provider raw-item authority | 4 | yes | Aggregated output is non-authoritative; one canonical assistant message is selected from raw items. |
| P2 | Ambiguous/incomplete output quarantine | 4 | yes | Distinct duplicates, incomplete, truncated, mixed, and malformed output execute zero actions. |
| P3 | Request-contract truth | 2 | yes | Every request and retry variant matches preflighted role, budget, protocol, and timeout. |
| S1 | Causal observation boundary | 4 | yes | Each Solver turn authorises one state-changing action or one bounded certified read-only observation batch. |
| S2 | Result continuity | 3 | yes | The exact complete latest Solver-requested result is visible before the next decision. |
| S3 | Submission coherence | 3 | yes | Submission is zero-action and impossible after unobserved change, protocol failure, stale evidence, or unchanged-state resubmit. |
| R1 | Architect semantic ownership | 5 | yes | Architect owns clauses, proof intent, strategy, false-success traps, context pins, dependencies, and pivots. |
| R2 | Compiler mechanical completeness | 5 | yes | Anchors, IDs, references, route existence, dependency shape, and field realisation fail closed; no semantic interpretation is added. |
| R3 | Config generation and reconfiguration | 5 | yes | Reconfiguration is disabled during certification; later path is generation-bound and owner-verified. |
| E1 | Immutable inspection registry | 5 | yes | Every accepted evidence reference resolves to one canonical registered inspection with route, target, generation, tool identity, hash, and ceiling. |
| E2 | Proof freshness | 5 | yes | Relevant mutation invalidates proof; uncertain dependency declarations conservatively invalidate on relevant generation change. |
| E3 | Evidence lineage/independence | 5 | yes | Derived representations preserve lineage and solver-authored transforms cannot self-certify strong semantic claims. |
| C1 | Completion conjunction | 8 | yes | Verifier completed plus a freshly ready deterministic gate and current findings/proof/process/integrity state are all required. |
| V1 | Verifier inspection protocol | 4 | yes | Verifier requests bounded real inspections and judges their returned current-state results. |
| V2 | Finding lifecycle | 3 | yes | Findings bind target/generation/owner/repair evidence and cannot be cleared by unrelated activity. |
| V3 | Failure ownership | 3 | yes | Solver, Architect/config, Verifier tooling, environment, provider, and kernel failures remain with the correct owner. |
| W1 | Workspace/artifact generations | 4 | yes | State-changing actions record before/after identity and a new generation; incomplete critical capture fails closed. |
| W2 | Process/service generations | 4 | yes | Real process identity, endpoint ownership, and fresh protocol observation bind service proof; restart invalidates it. |
| W3 | Helper transparency | 2 | yes | Helper subprocesses, state changes, network, outputs, and process identities remain observable. |
| X1 | Filesystem isolation | 2 | yes | Path-aware, symlink-safe containment passes traversal, sibling-prefix, and race-oriented tests. |
| X2 | Network policy | 2 | yes | Environment-declared scope is mechanically enforced; regex is not the boundary. |
| X3 | Secrets and late-generation quarantine | 1 | yes | Normal evidence is redacted and timed-out generations cannot alter active state, ledger, findings, or completion. |
| O1 | Context causality and bounded growth | 3 | no | Stable prefix and volatile causal packet avoid duplicated history and remain bounded over long runs. |
| O2 | Retained evidence access | 2 | no | Large outputs and historical evidence remain losslessly queryable by content-addressed handle. |
| G1 | Runner/grader integrity | 2 | yes | Official surfaces appear only after termination, all copies are checked and hashed, reward remains authoritative. |
| G2 | Source/evidence provenance | 2 | yes | Commit, tree, clean status, manifest, image, requests, initial/final state, spools, and final checksums are retained. |
| G3 | Evidence finalisation | 1 | yes | One final marker is written only after all writers close and checksums are final. |
| T1 | Production-bound invariant tests | 3 | yes | Every blocking invariant has positive, adversarial-negative, and production integration coverage. |
| T2 | Local and VM reproducibility | 2 | yes | Exact manifest-matching source passes the declared suites on supported local and fresh VM environments with explained skips. |

Total: 100 points.

## Required evidence per invariant

Every closure record must name:

- invariant ID;
- production owner;
- files changed;
- positive tests;
- adversarial negative tests;
- production integration tests;
- local command and result;
- VM command and result when required;
- commit and tree;
- clean status;
- remaining gaps;
- explicit PASS or NOT CLOSED verdict.

## Baseline at freeze

The integration candidate is commit
`0cbefbb47fc185baebfca7ceb41101b033554a2b`, selected as the strongest clean
proof-contract line, not yet declared final canonical source.

Known promotion blockers at freeze include:

- completed Verifier verdict can bypass deterministic non-readiness;
- proof generation is recorded but not enforced for freshness;
- evidence route/inspection/ceiling binding is incomplete;
- incomplete provider output can be returned as ordinary text;
- aggregated provider output is preferred;
- Solver turns permit multiple arbitrary actions;
- unrelated observations and memory queries can unlock resubmission;
- task-family inference exists in trusted EnvMap code;
- process/service proof is not fully generation-bound;
- path and network enforcement are not hard boundaries;
- initial snapshot and output-spool provenance are incomplete;
- V5-ported tests do not collect on the current integration candidate.
