# Harness engineering research

**What should a harness add to a model, and how would we know?**

From November 2025 to October 2026, one principal and a fleet of coding agents built five generations of
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

## The repository

| Folder | What's inside |
|---|---|
| [aether/](aether/) | The harness: the Gen 4 runtime (persistent worker, independent verifier, thin loop) and its tests |
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
