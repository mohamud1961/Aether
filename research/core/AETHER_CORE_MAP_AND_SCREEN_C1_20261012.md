# Aether Core: state map and pre-registered screen C1 (12 October 2026)

- **Authority:** principal, 12 October: "take over entirely", then "go; you now have a £5 budget to massively improve aether; include the reviewer in those tests (your call)".
- **Contamination:** the held-out evaluation traces were read on 11 October. Any later game-port-build row is **post-failure** and is labelled that way.

## 1. Current-state map (the previous solver live path → Aether Core)
| Mechanism | Evidence | Verdict |
|---|---|---|
| Structured file tools (write/edit/read) | the held-out evaluation: Aether built the interpreter-build binary-extract 3/3; Terminus 0/2 | **Keep** (Core: `read_file`/`write_file`/`edit_file`) |
| Deadline visibility | GLM tracked remaining time precisely | **Keep** (Core: clock on every tool result) |
| the earlier claim ledger finish review (the reviewer, failure-mode question) | S3+S4: the earlier claim ledger v4 + deadline 47/52 vs control 42/52. Claim-free reviewer caught 15/18 wrong finishes | **Keep the verifier role, re-implemented lean**: the claim-free state review in `aether/core/review.py`. Errors are recorded, never silent |
| the earlier claim ledger T1 diagnosis and card ritual | Crashed silently under background_v1 in every the held-out evaluation row | Not carried into Core. The old path is unchanged for reference |
| Progress checkpoints | Predict outcome (AUC 0.71 at 25%); GLM acted on them 1/13 | Not in Core v1; candidate for a later arm |
| Local token limiter | 112–179 s lost per interpreter-build row; 0 provider 429s | **Removed in Core**: the provider is the only rate authority (retry with Retry-After) |
| Context replay (reasoning, write bodies, old outputs) | About 2× Terminus input; up to 87 KB of replayed reasoning | **Core projection**: recent 4–9 turns verbatim; older turns as pointers, trimmed in cache-stable blocks |
| `run_command` + job tools + helper contract | Job tools unused; the helper contract cost 3 turns | **Replaced** by persistent named terminals (pty when available) with logs kept on disk |
| Environment-probe / context-packet JSON | Large, rarely used | **Removed** |
| Persistent terminal | Built in `harbor_executor.py`, never exposed | **Exposed** (fresh implementation, FIFO plus `script` pty) |

**Size:** Core is about 1,000 lines in 8 modules (largest 240), against about 84k lines on the previous solver path.

**Not built yet (later arms):** RLM-style Python REPL, sub-agents, image tool, checkpoints, model-written compaction.

## 2. Screen C1 (non-Frozen tasks; Core only; the previous solver is the historical reference)
| Arm | Flags |
|---|---|
| `core_off` | `--agent-mode aether-core --core-review off` |
| `core_reviewer` | `--agent-mode aether-core --core-review reviewer` |

- **Tasks** (1 episode per arm):
  - interpreter-build (the previous solver: 1/2 in screen 10, 2/2 in screen 3);
  - verified-compiler-build (the previous solver: solved in screen 10);
  - plus two short pool tasks chosen on the VM from the pool file before launch. They are recorded in the run log with their the previous solver history.
- **Smoke first:** repo-secret-recovery × both arms. Both rows must be valid, with the grader run and the run record present.

### Predictions (written before any Core row)
- Mean request ≤ 25k tokens on interpreter-build (the previous solver about 46–57k on mips-class rows).
- Zero client-side throttle waits; any provider 429 is retried and counted.
- interpreter-build: Core solves ≥ 1 of 2 rows (one per arm). verified-compiler-build: ≥ 1 of 2.
- the reviewer: 0 review errors. At most 1 hold per row. A hold on a row that is later solved counts as a false hold, and is reported.

### Falsifiers
- Core solves fewer of the 4 long-task rows than the previous solver's historical rate (about 60%) **and** is not faster to the first working artifact. Then Core is not better, and that is reported.
- Any review error, or a trace missing reasoning, calls, results or timings. Then it is a defect, fixed before any further row.

### Then (only if C1 is not falsified)
- game-port-build × 3 with the better Core arm, **labelled post-failure**, compared with the held-out evaluation Aether 0/3 and Terminus 0/2.

### Budget
- **Limit:** £5 total.
- **Estimates:** C1 plus smoke about £1.5–2; the make-doom follow-up about £1.
- **Controls:** stop at £4.5 estimated. The VM is deallocated when idle.
