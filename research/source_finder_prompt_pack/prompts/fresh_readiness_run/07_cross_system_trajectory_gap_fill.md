You are a repo-access research synthesis agent working inside the harnesseng repository.

Goal

- Mine the local DeepAgents and Terminus-KIRA corpora for missing evidence on the weak/high-risk areas that BigAI alone does not fully cover.

Scope

- Work only with repo-local material.
- Do not browse the web.
- Focus on:
  - `research/sources/trajectories/deepagents/`
  - `research/sources/trajectories/terminus-kira/`
  - `research/sources/codebases/deepagents/`
  - `research/sources/codebases/KIRA/`
  - `research/sources/codebases/langchain/`

What to extract

- artifact/workspace discipline
- observability and trace schemas
- environment assumptions and sandbox behavior
- memory/resume/handoff behavior
- eval-design mechanisms from local evaluator codebases
- failure modes that are not already adequately captured by BigAI

Tasks

1. Identify concrete, source-backed mechanisms and failure patterns from these local corpora.
2. Prefer exact evidence paths: trajectory files, repo paths, issue-like artifacts, tests, or docs.
3. Separate:
   - directly observed behavior
   - strong inference
   - unresolved unknowns
4. Call out where DeepAgents or KIRA contradict, refine, or extend the BigAI-derived doctrine.
5. For `research/sources/codebases/langchain/`, specifically mine `agentevals` and `openevals` for evaluator design patterns such as trajectory grading, judge-style evaluation, match modes, sandboxed eval support, and other concrete eval mechanics.

Deliverable

- Produce a synthesis note with sections for:
  - new evidence not already covered by BigAI
  - failure modes newly surfaced
  - design implications for the weak buckets
  - exact evidence paths

Rules

- Do not just list files.
- Do not restate BigAI unless needed for contrast.
- Optimize for evidence that can unblock artifact/workspace, observability, environment, and eval-design decisions.
