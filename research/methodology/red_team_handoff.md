# Red Team Review: Agentic Harness Experimental Methodology

## Your Role

You are a red team reviewer. Your job is to **challenge, stress-test, and improve** the experimental methodology described below. Be adversarial. Find the holes. Suggest better alternatives. Don't be polite about it.

Specifically:
1. **Challenge the eval selection.** Are these the best evals? Are there better ones we missed? Are any of these a waste of time?
2. **Challenge the experiment ordering.** Is the sequence optimal? Would a different order yield faster or more reliable results?
3. **Challenge the assumptions.** What are we assuming that might be wrong?
4. **Suggest alternatives.** For every criticism, propose a concrete alternative.
5. **Evaluate feasibility.** Given budget constraints (GPT Plus limits first, then API — hundreds, not thousands of dollars), is this plan realistic?

After your review, we'll iterate together to reach an agreed methodology. Then it's research time.

---

## Project Context

### Mission
Build the best possible agentic harness through systematic experimentation. Not "our" approach — the **objectively best** approach. Whatever architecture wins the experiments wins, period.

### Repo Structure (`harnesseng`)
```
blocks/           ← Composable harness components (6 dimensions)
  context/        ← Context/state management variants
  execution/      ← Execution loop variants
  orientation/    ← Task orientation variants
  recovery/       ← Error recovery variants
  tools/          ← Tool surface variants
  verification/   ← Verification strategy variants
research/         ← Research inputs and analysis
  analysis/       ← Structured findings (patterns.md, failure_modes.md, lego_dimensions.md)
  sources/        ← Raw material (papers, trajectories, codebases)
    trajectories/BigAI/  ← 89 TerminalBench task trajectories from top-3 agent
runner/           ← Experiment infrastructure
experiments/      ← Configs and results
evals/            ← Evaluation harnesses
tasks/            ← Task definitions (easy/medium/hard)
```

### Core Rules
- Each block < 200 lines, independently swappable
- Same model across all experiments (model is the control variable)
- Log everything — full trajectories for post-hoc analysis
- All blocks of same type implement the same interface

### Key Interfaces
```python
OrientationBlock.orient(task_prompt, env_info) -> initial_context
ToolBlock.get_tools() -> list[tool_definitions]
ExecutionBlock.run_loop(model, tools, context, max_steps) -> result
ContextBlock.manage(history, new_observation) -> updated_history
VerificationBlock.check(task, workspace_state) -> verified: bool
RecoveryBlock.handle_error(error, history) -> recovery_action
```

---

## Current Methodology (What You're Reviewing)

### The 3-Phase Machine

**Phase 1: Research** — Analyze public trajectories, papers, eval winners. Extract patterns per dimension. Output: variant hypotheses backed by evidence.

**Phase 2: Variant Creation** — Build 3-4 block variants per dimension. Each under 200 lines. Each implements the same interface. Variants range from simple baseline to experimental (e.g., graph-based context).

**Phase 3: Experiments** — Test one dimension at a time. Each experiment swaps ONE block variant while holding all others at current best. Sequential ablation with greedy winner selection.

### Bootstrapping: Default Configuration
Before any experiments, a minimum viable harness is needed:
- Orientation: Pass task prompt as-is
- Tools: Shell + file read/write
- Execution: Simple loop (act → observe → repeat)
- Context: Full conversation history
- Verification: Run tests at end only
- Recovery: Retry once, then give up

### Experiment Order (Current Proposal)
```
1. Execution Loop      ← Eval: TerminalBench
2. Orientation         ← Eval: TerminalBench
3. Tool Surface        ← Eval: τ-bench
4. Context Strategy    ← Eval: ContextBench
5. Verification        ← Eval: TerminalBench (internal measurement)
6. Error Recovery      ← Eval: τ-bench + custom failure injection
7. Full Validation     ← All evals combined
```

Rationale: Execution loop first (model spends 90% of time there), context strategy at position 4 (needs long runs to show signal), verification and recovery last (refinements that improve a working agent, can't save a broken one).

### Eval Selection (Current Proposal)

**Kept:**
| Eval | Tests | Why Kept |
|---|---|---|
| TerminalBench (3-5 tasks: easy/medium/hard/impossible) | End-to-end coding task completion, Docker + pytest | Primary target. 89 BigAI trajectories as baseline. Workhorse eval. |
| GAIA | Multi-step reasoning, tool orchestration, web browsing | Planning + tool orchestration quality. Cross-validation in exp 7. |
| τ-bench | Stateful API interactions, error recovery, policy compliance | Tool calling patterns + error recovery. APIs fail by design. |
| ContextBench (Letta or coding agent variant) | Long-term memory retrieval, codebase understanding | Directly tests context retrieval quality. THE eval for graph vs flat context. |

**Dropped:**
| Eval | Why Dropped |
|---|---|
| MRCR | Tests model recall, not harness memory management |
| BFCL v4 | Tests function calling syntax accuracy — model capability, not harness |

### Eval Coverage Matrix
```
                    TerminalBench   GAIA   τ-bench   ContextBench
Execution Loop         ✅✅          ✅       ✅         ⬜
Orientation            ✅✅          ✅       ⬜         ⬜
Tool Surface            ✅           ✅      ✅✅        ⬜
Context Strategy        ✅           ⬜       ✅        ✅✅
Verification           ✅✅          ⬜       ✅         ⬜
Error Recovery          ✅           ⬜      ✅✅        ⬜
```

### Baseline Strategy
- NO custom baseline needed — use public data
- BigAI trajectories (89 tasks, top-3 TerminalBench agent) already in repo
- Claude Code TerminalBench results publicly available
- GAIA, τ-bench, ContextBench have published leaderboards and winner approaches
- Extract orchestration patterns from winners → turn into variant hypotheses

### Success Metrics
- **Primary:** Pass rate + consistency (variance across runs)
- **Secondary:** Step efficiency, token cost
- **Diagnostic:** Recovery rate, progress on unsolved tasks

---

## Open Questions (Answer These)

1. **Is the sequential ablation approach (greedy search) sufficient?** Or do dimension interactions make it necessary to test combinations? If so, which combinations?

2. **Are 3-5 TerminalBench tasks enough for statistical signal?** Or do we need more tasks to distinguish variant performance from noise?

3. **Is the eval suite complete?** Are there evals we should add — particularly for verification, tool methodology, or planning quality?

4. **Is the ordering optimal?** Should any dimension be tested earlier or later than proposed?

5. **Are we missing a dimension entirely?** The current 6 (orientation, tools, execution, context, verification, recovery) — is there a 7th axis that matters?

6. **Is the default configuration the right control?** Does the simplicity of the default bias results? (E.g., "full conversation history" as default context might perform surprisingly well, making it hard for alternatives to beat.)

7. **What about prompt engineering as a dimension?** System prompts, role definitions, chain-of-thought instructions — should this be its own axis or is it embedded in each block?

8. **Budget feasibility.** With ~$500-1500 total budget for API calls (plus GPT Plus for development), is the full 7-experiment sequence realistic? What corners can we cut without losing signal?

---

## What We Need Back From You

1. A critique of each eval choice with concrete alternatives if applicable
2. A critique of the experiment ordering with a counter-proposal if you disagree
3. Any evals, dimensions, or approaches we've completely missed
4. A feasibility assessment given the budget
5. Your recommended changes to reach an agreed methodology

Be harsh. The methodology needs to be bulletproof before we start spending money on experiments.
