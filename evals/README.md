# Evaluations

How do you know a harness helped? This programme built 151 evaluations over eleven months and learned
mostly that the measurement fails before the agent does. Here you'll find the current tasks, the methods
that came out of it, and every evaluation ever built.

**Start with:** [STORY.md](STORY.md) explains how the evaluations evolved and why each layer exists.

## Targets: what the tasks test

| Target | Tasks | Probes |
|---|---|---|
| [Tooling](tooling/) | 4 | Exact tool-call contracts, schema drift, MCP and skill registries |
| [Filesystem](filesystem/) | 4 | Decoy targets, layered config, repo recovery, manifest integrity |
| [Retrieval](retrieval/) | 2 | Exact evidence from noisy, stale and conflicting sources |
| [Execution](execution/) | 5 | Environment bootstrap, runtime contracts, process truth, service lifecycle |
| [Context](context/) | 2 | State over long logs and handoffs, after rollbacks and renames |
| [Orchestration](orchestration/) | 3 | Delegation fidelity, worker handoffs, noisy multi-step workflows |
| [Verification](verification/) | 2 | Exact serialization and semantic equivalence against a spec |
| [Recovery](recovery/) | 3 | Transport faults, background job lifecycles, resuming a crashed migration |
| [Safety](safety/) | 3 | Instructions injected via tool output, out-of-scope edits, counting under scope rules |

Each task folder holds `prompt.md`, `workspace/`, a hidden `grader/`, a `reference/` solution,
`known_bad/` states, `careless/` agents and `ceiling.md`. Tasks marked `debug` run candidate code inside
the grader and need a sandbox.

## Methods

[Known-bads and careless agents](methods/known-bads-and-careless-agents.md) ·
[Pre-registration and sentinels](methods/preregistration-and-sentinels.md) ·
[Tournaments and attribution](methods/tournaments-and-attribution.md) ·
[Whole-harness boards](methods/whole-harness-boards.md) ·
[Held-out evaluation](methods/held-out-evaluation.md) ·
[Measurement validity](methods/measurement-validity.md) ·
[Row-level audit](methods/row-level-audit.md) ·
[Workbench qualification](methods/workbench-qualification.md)

## Everything ever built

[catalogue.md](catalogue.md): all 151 evaluations, one line each, with grade and result.

## Run the gates

```bash
pip install -e .
python -m harness_evals validate-graders evals
python tools/check_tasks.py evals
```
