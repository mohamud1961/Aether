# Collaboration Workspace

This folder holds structured multi-agent collaboration artifacts for the project.

It is the canonical place for:

- task packets used by multiple agents
- separate agent outputs for the same artifact
- synthesis artifacts
- explicit decision notes

It is not the canonical research ledger and not the git handoff area.

## Why this exists

The project may use multiple strong agents, but the canonical record should not be one shared rolling chat. Collaboration should be:

- stage-aware
- artifact-scoped
- auditable
- separable from the historian ledger

## Recommended layout

```text
tracking/collab/
  stage_02_synthesis/
    mechanism_map/
      brief.md
      inputs/
      outputs/
        gpt54_parallel.md
        gemini_parallel.md
        claude_parallel.md
      synthesis/
        principal_synthesis.md
      decision.md
```

## File roles

- `brief.md`: the task packet, objective, exclusions, and output schema
- `inputs/`: source pointers, snapshots, or supporting notes
- `outputs/`: separate outputs from each participating agent
- `synthesis/`: final synthesis or arbitration artifact
- `decision.md`: the explicit decision or next-step conclusion
- `TASK_PACKET_TEMPLATE.md`: reusable template for `brief.md`

## Rules

1. Do not use one shared file for all agent answers.
2. Keep agent outputs separate until synthesis.
3. Every collaboration workspace should map to one stage and one artifact.
4. If the work is materially important, emit a `RAW_LEDGER_UPDATE` citing the relevant files here.
5. Do not treat this folder as the canonical ledger. The historian still owns `tracking/ledger/`.
6. Only files explicitly named by the active `brief.md` or `decision.md` are mandatory outputs. README files, placeholder analysis docs, and scaffold notes are not automatically required deliverables.
