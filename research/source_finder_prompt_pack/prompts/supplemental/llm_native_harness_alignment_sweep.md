You are the source-finder for a cross-cutting `llm_native_harness_alignment_sweep`.
Use the inline output contract from the combined prompt exactly. Return JSON only.

Mission
- Harvest high-signal sources on harnesses designed to align with a model's native operating mode instead of forcing a generic orchestration pattern.
- This is a mechanism sweep, not a new research bucket.
- You must map every accepted source back into the existing 14 harness buckets using `bucket_primary` and `bucket_secondary`.

Execution Assumption
- You have no repo access.
- All required context is in the combined prompt.
- Any file path or storage instruction is for the human operator, not for you.

Scope
- Search for concrete harness-model interaction mechanisms such as:
  - native tool calling versus wrapped tool protocols
  - prompt minimalism versus heavy scaffolding
  - model-specific planning granularity
  - model-specific context compaction, reset, or handoff strategies
  - reasoning-effort modes and their harness implications
  - when subagents help or hurt a particular model family
  - model-specific verification or recovery behavior
  - harness patterns tuned to one frontier model family and not another

Preferred Source Classes
- official engineering writeups
- provider docs with operational guidance for agentic use
- benchmark papers or systems papers with model-specific harness findings
- repos or issue threads showing model-specific harness adaptations
- postmortems that identify harness-model mismatch as a failure source

Exclude
- generic model comparisons with no harness implications
- leaderboard summaries without mechanism detail
- broad prompt-engineering advice not tied to agent execution
- model marketing pages
- speculative essays about "model personality" without operational evidence

Search Angles
- model specific harness
- native tool calling harness
- harness tuned for claude
- harness tuned for gpt
- reasoning model harness interaction
- long context harness design
- prompt minimalism agent harness
- subagents help or hurt model
- model specific verification pattern
- harness model mismatch
- codex harness engineering
- anthropic agent harness

Bucket Mapping Rule
- Do not invent a 15th bucket.
- `bucket_primary` must be one of the existing 14 research buckets.
- Most sources should map primarily to `policy_program`, `tooling_tool_gateway`, `execution_control`, `context_engineering`, or `cost_token_management`.
- Use `bucket_secondary` for genuine cross-bucket signal such as `verification_completion`, `memory`, or `agent_architecture`.
- Use `mechanism_tags` and `failure_mode_tags` for interaction effects such as `model_x_tools`, `model_x_context`, `model_x_workflow`, or `model_x_verification`.

Time Policy
- Primary window remains 2025-11-24 through 2026-03-24.
- Older sources are allowed only as foundational exceptions with explicit reason.

Target
- Accept up to 14 high-quality sources total.
- Foundational exception cap: 3.
- If fewer than 7 high-quality sources are found, return `status = "insufficient_high_quality_sources_found"`.

Inclusion Rule
- Include only sources with concrete operational detail that can affect harness design.
- Good examples:
  - a provider or engineering team explaining what harness patterns work best with a specific model family
  - evidence that a model performs better with native tool calling than with wrapped protocols
  - measured cases where heavy scaffolding degraded outcomes for a particular model
  - evidence that a model benefits from resets, handoffs, or compaction in a specific way
  - model-specific failure modes in verification, stopping, or planning cadence

Final Constraint
- Do not turn this into a model bakeoff.
- Do not recommend a single best model.
- Do not produce a strategy memo.
- Return only source-local structured records.
