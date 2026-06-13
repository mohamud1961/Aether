# Synthesis Team Spec

## Status

Working synthesis-stage operating spec as of 2026-04-02. This is the recommended structure for turning the raw research corpus into mechanism-level project artifacts.

This is not a permanent always-on team. It is a stage-specific operating model for the synthesis phase.

## Purpose

The raw research corpus is currently organized mostly by source origin:

- papers
- docs
- repos
- trajectories
- raw bucket outputs
- informal links

That is good for intake, but not good enough for downstream design work.

The synthesis phase must convert the full frozen corpus into a mechanism- and failure-organized evidence base that can drive:

- eval architecture
- variant design
- baseline harness design
- experiment policy

## Core principle

Do not spin up a giant permanent team.

Do not let one principal agent do all synthesis alone.

Use a bounded synthesis cell per artifact, routed by the principal agent.

At important moments, default to adversarial review rather than treating synthesis outputs as accepted on first pass.

## Synthesis stages

### Stage 2A. Synthesis prep

Goal:

- reorganize the full frozen corpus into a usable evidence base

Outputs:

- indexed evidence inventory
- evidence confidence labels
- source-type labels
- initial mapping from evidence to harness dimensions
- trajectory index by failure and mechanism
- codebase index by subsystem relevance
- an explicit corpus map for all in-scope evidence classes

### Deep Synthesis

Goal:

- derive high-value cross-source conclusions from the full frozen corpus using a major multi-agent analysis operation

Outputs:

- mechanism map
- failure taxonomy
- evidence-backed claims
- contradictions and uncertainty notes
- eval implications
- candidate variant families

Important:

- deep synthesis is not a single deterministic pass
- all major evidence classes remain in scope:
  - papers
  - docs
  - informal sources
  - trajectories
  - codebases
  - eval repos
  - eval captures

## Recommended synthesis cell

### 1. Principal project steward agent

Role:

- stage manager and synthesis owner

Reads:

- current project spine
- active research outputs
- specialist outputs for the current artifact

Produces:

- `brief.md`
- synthesis plan for the artifact
- final synthesis artifact
- `decision.md`

Must do:

- choose the collaboration mode
- choose which specialists are needed
- keep artifacts bounded
- escalate major decisions to the human owner

Must not:

- silently redefine project goals
- absorb historian responsibilities
- treat unsupported claims as settled truth

### 2. Research organizer / evidence indexer

Role:

- turn source-organized material into synthesis-ready evidence structure

Suggested reusable prompt:

- `prompts/synthesis_prep_agent_prompt.md`

Reads:

- accepted corpus manifests
- source records
- source mirrors
- supplemental sweep outputs
- informal-link inventories

Produces:

- evidence inventory for the artifact
- source-confidence labels
- source-type labels
- mechanism/failure relevance tags

Good outputs:

- `evidence_inventory.md`
- `source_tagging.md`
- `evidence_matrix.csv` or structured equivalent if needed

### 3. Trajectory and failure analyst

Role:

- extract the highest-value evidence from real agent behavior

Reads:

- trajectory text files
- run tarballs and trace artifacts
- eval attempt notes
- failure logs and verification outputs

Produces:

- failure patterns
- control-policy observations
- recovery and verifier observations
- behavior-derived mechanism candidates

Good outputs:

- `trajectory_findings.md`
- `failure_clusters.md`
- `control_policy_notes.md`

Priority:

- highest

This role is critical because trajectories are one of the most valuable evidence sources in the project.

### 4. Codebase and eval analyst

Role:

- extract design patterns from source code and mirrored eval repos

Suggested reusable prompt:

- `prompts/synthesis_prep_eval_inventory_agent_prompt.md`

Reads:

- mirrored codebases under `research/sources/codebases/`
- local `evals/`, `runner/`, and `blocks/` where relevant
- mirrored eval repos including LangChain `agentevals` and `openevals`

Produces:

- mechanism implementations
- eval-pattern notes
- interface and workflow observations
- reuse candidates and cautions

Good outputs:

- `codebase_patterns.md`
- `eval_pattern_notes.md`
- `implementation_mechanisms.md`

### 5. Literature and informal-source analyst

Role:

- extract conceptual and engineering signal from papers, official docs, blogs, issues, and informal sources

Reads:

- papers
- official docs
- engineering writeups
- issues
- informal source collections

Produces:

- source claims with confidence notes
- terminology normalization
- concrete mechanism and failure insights
- explicit notes on what is asserted versus observed

Good outputs:

- `literature_claims.md`
- `informal_signal.md`
- `terminology_map.md`

Important:

- informal sources are allowed and often valuable
- they must stay labeled as informal or anecdotal where appropriate

### 6. Contradiction and red-team analyst

Role:

- attack weak synthesis

Suggested reusable prompt:

- `prompts/synthesis_prep_red_team_agent_prompt.md`

Reads:

- all specialist outputs for the current artifact
- draft synthesis from the principal agent when needed

Produces:

- contradiction list
- unsupported-claim flags
- alternative interpretations
- missing-evidence warnings

Good outputs:

- `contradictions.md`
- `red_team_notes.md`

### 7. Historian agent

Role:

- separate canonical recorder

Reads:

- raw `RAW_LEDGER_UPDATE` handoffs

Produces:

- canonical ledger entries under `tracking/ledger/`

Important:

- not part of synthesis arbitration
- should remain outside the main synthesis cell

## Artifact-level activation

Do not activate every role for every artifact.

Recommended activation by artifact:

### Mechanism map

- principal agent
- research organizer
- trajectory/failure analyst
- codebase/eval analyst
- literature/informal analyst
- contradiction analyst

### Failure taxonomy

- principal agent
- trajectory/failure analyst
- research organizer
- literature/informal analyst
- contradiction analyst

### Eval implications

- principal agent
- codebase/eval analyst
- trajectory/failure analyst
- literature/informal analyst
- contradiction analyst

### Variant-family seeds

- principal agent
- trajectory/failure analyst
- codebase/eval analyst
- contradiction analyst

## Collaboration mode by artifact

### Mechanism map

Use:

- blind parallel for first-pass extraction
- then synthesis

### Failure taxonomy

Use:

- blind parallel for first-pass extraction
- then contradiction review
- then synthesis

### Eval implications

Use:

- role-sequenced collaboration

Suggested flow:

- proposer
- critic
- falsifier
- synthesizer

### Variant-family seeds

Use:

- hybrid

First:

- blind parallel seed proposals

Then:

- role-sequenced pruning

## What each synthesis artifact should answer

### Mechanism map

- what mechanisms exist
- what problem each mechanism addresses
- what evidence supports it
- what failure modes it is meant to reduce
- what likely evals would discriminate it

### Failure taxonomy

- how agents fail in practice
- where the failure appears
- what evidence shows it
- whether it looks like model, harness, or environment failure
- what mechanisms might mitigate it

### Eval implications

- what should be measured
- what should be held fixed
- what could be gamed
- what should become atomic vs dependent-part vs interaction evals

### Variant-family seeds

- what can change
- what should stay fixed
- what simple contenders must exist
- what complexity needs justification

## Synthesis run order

### Pass 1. Prep and organization

1. principal agent defines the artifact and task packet
2. research organizer builds the evidence inventory
3. principal agent approves the evidence scope

### Pass 2. First independent analysis

1. relevant specialists work independently
2. outputs are stored separately
3. no premature convergence

### Pass 3. Contradiction and pressure test

1. contradiction/red-team analyst attacks the combined picture
2. principal agent identifies unresolved disputes

### Pass 4. Synthesis

1. principal agent writes the synthesis artifact
2. principal agent writes explicit open questions
3. human owner reviews the artifact

### Pass 5. Ledger capture

1. a raw `RAW_LEDGER_UPDATE` is emitted citing the synthesis files
2. historian later promotes material conclusions into the canonical ledger

## Storage conventions

Canonical collaboration location:

- `tracking/collab/stage_02_synthesis/`

Recommended workspace shape:

```text
tracking/collab/stage_02_synthesis/
  mechanism_map/
    brief.md
    inputs/
    outputs/
      organizer.md
      trajectory_analyst.md
      codebase_eval_analyst.md
      literature_informal_analyst.md
      contradiction_analyst.md
    synthesis/
      principal_synthesis.md
    decision.md
```

## What should happen immediately after raw research ends

The first synthesis tasks should be:

1. organize the evidence base
2. build the mechanism map
3. build the failure taxonomy
4. derive eval implications

Do not start with:

- full variant proliferation
- full automation
- eval tournaments

## Recommended current decisions

1. Synthesis should explicitly include trajectories, source code, eval repos, papers, official docs, and informal sources.
2. Trajectories should be treated as one of the highest-priority evidence classes.
3. Synthesis should start with organization, not with immediate cross-source theorizing.
4. The principal agent should route synthesis work, but not do all synthesis alone.
5. The historian should remain separate from synthesis arbitration.

## Actions taken in this pass

This pass defines the concrete synthesis-team structure, role boundaries, artifact activation rules, storage conventions, and run order for the synthesis phase.
