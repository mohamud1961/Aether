# Deep Synthesis Setup

Date: 2026-04-07

Artifact

- `deep_synthesis_setup`

Current judgment

- Deep Synthesis execution is open.
- The setup surface now needs to reflect the compressed 14-wave model, the support tracks, and the cost-aware agent model.

Required execution surfaces

- shared policy prompt:
  - `prompts/deep_synthesis_shared_policy_prompt.md`
- main-lane prompts:
  - `prompts/deep_synthesis_trajectory_failure_analyst_prompt.md`
  - `prompts/deep_synthesis_codebase_source_reconstruction_analyst_prompt.md`
  - `prompts/deep_synthesis_literature_papers_docs_analyst_prompt.md`
  - `prompts/deep_synthesis_informal_issues_postmortems_analyst_prompt.md`
  - `prompts/deep_synthesis_eval_benchmark_analyst_prompt.md`
  - `prompts/deep_synthesis_contradiction_analyst_prompt.md`
  - `prompts/deep_synthesis_checklist_adjudicator_prompt.md`
  - `prompts/deep_synthesis_eval_implications_role_prompt.md`
  - `prompts/deep_synthesis_variant_pruning_role_prompt.md`
- operating docs:
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_PHASE_AND_WAVE_OPERATING_PLAN.md`

Serious-wave main roster

- `trajectory/failure analyst`
- `codebase/source-reconstruction analyst`
- `literature/papers/docs analyst`
- `informal/issues/postmortems analyst`
- optional fifth:
  - `eval/benchmark analyst`

Why this is the default

- it keeps behavior-first grounding
- it keeps source depth
- it keeps formal and informal evidence separated
- it avoids flattening papers and operator signals into one vague external lane

Bounded support sub-agents

- should be standard for large serious waves
- should be launched under the main analysts
- should produce explicit support artifacts
- should not replace main-lane synthesis

Model recommendations

Stable principal:

| Role | Model | Why |
| --- | --- | --- |
| principal steward and final synthesizer | `GPT-5.4 xhigh` | strongest available synthesis and governance model |

Main serious-wave defaults:

| Role | Model | Why |
| --- | --- | --- |
| trajectory/failure analyst | `GPT-5.4 xhigh` | strongest behavior and cross-run synthesis |
| codebase/source-reconstruction analyst | `GPT-5.3 Codex xhigh` | strongest code-grounded and architecture-grounded read |
| literature/papers/docs analyst | `GPT-5.4 xhigh` | strongest formal-source synthesis |
| informal/issues/postmortems analyst | `GPT-5.4 xhigh` | strongest contradiction-heavy narrative synthesis |
| eval/benchmark analyst | `GPT-5.4 xhigh` | strongest evaluator-logic synthesis when activated |
| contradiction analyst | `GPT-5.4 xhigh` | strongest GPT-side skeptical reviewer |
| checklist adjudicator | `GPT-5.4 xhigh` | strongest GPT-side audit pass |

Support-sub-agent defaults:

| Support job family | Recommended model | Why |
| --- | --- | --- |
| source file discovery and subsystem maps | `GPT-5.3 Codex high` | code-native bounded excavation |
| trajectory inventory, matrices, and link tables | `GPT-5.4-mini high` | cheaper bounded structuring work |
| literature grouping and quality triage | `GPT-5.4-mini high` | cheaper bounded clustering work |
| informal clustering and contradiction tables | `GPT-5.4-mini high` | cheaper bounded clustering work |
| eval route maps and verifier/grader extraction | `GPT-5.4-mini high` | cheaper bounded extraction before synthesis |

External gate reviewers

- `Gemini 3.1 Pro`
  - use for breadth or long-context gate checks
  - not a default parallel main lane
- `Claude Opus 4.6`
  - use for adversarial contradiction or acceptance gates
  - not a default parallel main lane

Per-artifact collaboration mode

| Artifact | Mode |
| --- | --- |
| `mechanism_map` | 4 main lanes, optional eval fifth, bounded support sub-agents, contradiction, principal synthesis, checklist |
| `failure_taxonomy` | 4 main lanes, optional eval fifth, bounded support sub-agents, contradiction, principal synthesis, checklist |
| `eval_implications` | role-sequenced critique |
| `variant_family_seeds` | seed proposals plus pruning and contradiction gates |

Prompt workflow note

- The setup now provides the stage structure, lane roster, support-track model, and model guidance.
- A dedicated prompt-engineering agent can now draft or refresh the actual wave and lane prompts against this stable execution surface without changing stage governance again.
