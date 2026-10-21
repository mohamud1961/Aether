# Harness engineering research

**What should a harness add to a model, and how would we know?**

From late 2025 to October 2026, one principal and a fleet of coding agents built five generations of
agent harness. The same period produced 151 evaluations of those harnesses, and an audit of nearly every
result. Most of what we learned came from measurements that turned out to be wrong.

## Five findings

1. **Cheaper calls made trajectories more expensive.** Cutting context bytes by 29% raised model calls by 56%.
2. **A pre-registered falsifier fired on our own harness.** On sealed held-out tasks it solved 5/9 against a stock agent's 4/6.
3. **A completion verifier needs its own evaluation.** One verifier ran 0 real checks in 20 runs while reporting success.
4. **Most measured wins were measurement artefacts.** A "78.5%" batch was a rate-limit storm: 456 of 482 verifier rounds errored.
5. **Review without the agent's claims catches more.** 15/18 wrong finishes caught, against 10/18 with claims.

Details and limits: [research/findings.md](research/findings.md). How the run loop broke and was fixed:
[research/run-loop-engineering.md](research/run-loop-engineering.md). How failures became evals became harness
changes: [research/outer-loop.md](research/outer-loop.md).

## Matched results

The table includes matched comparisons and one held-out campaign with unequal valid-row counts.
Denominators and limits are shown; the held-out row is not a paired estimate of lift.

| Comparison | Aether | Other side | Reading |
|---|---|---|---|
| Gen 4 candidate vs a stock reference agent, sealed held-out tasks | 5 of 9 | 4 of 6 | The pre-registered falsifier fired: no lift |
| Aether Core vs a stock reference agent, GLM-5.3-Flash, 18-row board | 12 of 18 | 12 of 18 | Tie |
| Finish review without the agent's claims vs with them, offline bench | 15 of 18 wrong finishes caught | 10 of 18 | Better without the claims; offline only |
| Structured file tools vs a stock reference agent, one build task | 3 of 3 | 0 of 2 | One task; small sample |
| Cache-stable context vs the earlier context, 16 rows each | 10 of 16 at $0.014 per row | 10 of 16 at $0.031 | Same passes at half the cost |
| Requirement ledger vs none, 15 rows each | 6 of 15 | 8 of 15 | Worse; not kept |

No generation has a frozen benchmark win against a stock agent. Details: [research/generations/](research/generations/).

## How this was built

One principal directed the work, and coding agents did most of the implementation, analysis and auditing: Codex
from spring, ChatGPT in late summer, and from 8 October Claude in Claude Code, orchestrating Sonnet and Haiku
subagents. Gen 5 (`aether/core/`) was built in that last phase; its commits carry their `Co-Authored-By` trailers.
The operating model, its review gates and the incidents that shaped them are in [workflows/](workflows/). Where to
find evidence of specific skills: [docs/evidence-map.md](docs/evidence-map.md).

## The repository

| Folder | What's inside |
|---|---|
| [aether/](aether/) | The harness: Aether Core, the current lean loop ([aether/core/](aether/core/)), and the Gen 4 runtime it replaced (persistent worker, independent verifier, thin loop) |
| [harness_evals/](harness_evals/) | The eval runner: task format, sandboxed runs, grader validity, trial rows, statistics |
| [docs/](docs/) | The harness vision, architecture layers, engineering standards and the No Fake Work rule |
| [evals/](evals/) | 28 tasks across nine targets, each validated against known-bad states and careless agents. Eight evaluation methods, and a catalogue of all 151 evaluations |
| [research/](research/) | The findings, run-loop engineering, the outer loop, a synthesis of 312 external runs, five harness generations, postmortems |
| [workflows/](workflows/) | How the work was run: the principal's role, governance, orchestrating agent fleets |
| [notebook/](notebook/) | Decisions, turning points and a timeline |

## Quick start

```bash
pip install -e .
python -m harness_evals validate-graders evals
```
