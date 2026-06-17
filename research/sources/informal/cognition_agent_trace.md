# Article

**URL:** https://cognition.ai/blog/agent-trace

## Content

January 29, 2026 Agent Trace: Capturing the Context Graph of Code by The Cognition Team In this article: We’re excited
to join Cursor, Cloudflare, Vercel, git-ai, Google Jules, Amp, OpenCode and others in support of [Agent
Trace](https://agent-trace.dev/) . As described in the spec, Agent Trace is an open, vendor-neutral spec for recording
AI contributions alongside human authorship in version-controlled codebases. (fun fact: above video was vibed in
Windsurf entirely with the [Remotion skill](https://x.com/Remotion/status/2013626968386765291) !) Reductively, you can
explain this as “a standard way to check in prompts with every commit”, but the spec is actually far more robust and
thoughtfully designed than capturing just prompts. [
](https://cdn.sanity.io/images/2mc9cv2v/production/79ef526eebcee5989d0619a29847ddaf4764e52b-3600x1890.png) The Central
Problem: Throwing Away Context Foundation Capital recently wrote a viral piece on [Context
Graphs](https://foundationcapital.com/context-graphs-ais-trillion-dollar-opportunity/) that they define as: “ a living
record of decision traces stitched across entities and time so precedent becomes searchable. Over time, that context
graph becomes the real source of truth for autonomy – because it explains not just what happened, but why [it
happened].” Git was [made](https://x.com/swyx/status/1536832603411451905?lang=en) in 2005 when the normal state of code
collaboration was to email patches of code back and forth between developers. In other words, commits were expensive
/bandwidth constrained, so we committed the bare minimum of what we could: line differences. 20 years later, we have
shifted from bandwidth constrained to context constrained. You -can- kloodge things by simply adding prompts as comments
and checking them into git, but your code would soon be completely buried under a mountain of comments and your human
and AI colleagues would hate you. Instead, Agent Trace does the smart thing - attribute each change (potentially a git
commit, but potentially other more atomic changes) to the specific conversation and line ranges that were associated
with that change: [
](https://cdn.sanity.io/images/2mc9cv2v/production/01b3de3cc23312419f0a3a46a11da484584eb170-762x729.png) Every one of us
in the coding agents industry has independently developed a url identifier for the "chat" or "conversation" or
"trajectory" (whatever you call it) where you can retrieve the (potentially long, potentially multimodal) context that
would otherwise be impractical to store in an agent trace. This one basic contract means that a repo with associated
Agent Traces will always be able to link back to the context that created it. As a nice bonus, it helps keep PII and
other sensitive information out of the agent trace store and top-level access for compatible coding agents that consume
Agent Traces. Useful for Eng Management To jog your creativity, here are some of the internal tools we've already built
that show what Agent Trace can unlock (all data is mock data unfortunately): File Viewer that can attribute/blame AI vs
Humans: [ ](https://cdn.sanity.io/images/2mc9cv2v/production/9e113d49959851da0c47c478318877177d4e9c7c-1548x529.png)
PR-level breakdown of feature development [
](https://cdn.sanity.io/images/2mc9cv2v/production/367645ee0ec755d3cfadbec4aa7f9c30906b3a60-1271x819.png) New interfaces
for PR review ( [something we're VERY interested in](https://cognition.ai/blog/devin-review) ) with full development
context [ ](https://cdn.sanity.io/images/2mc9cv2v/production/7ecdce0497d1f6c8619a141848b63e94149602dd-1501x1077.png) In
a scaled org with multiple coding agents and tools and humans all contributing code, you can imagine some pretty
powerful management-level dashboards and data-driven decisions made once everyone outputs Agent Traces. Agent Traces
make development legible. Useful for Individual Agent Performance However we don't mean to cast Agent Traces as "just
use it so you know which AI to blame" or "just for pretty dashboards". With Agent Traced codebases, we think your agents
will become a lot smarter and overall waste a lot less time spinning and reinventing wheels. In 2025, the world learned
that [including the hidden reasoning artifacts and prior tool calls of models like
GPT5](https://x.com/prashantmital/status/1964850633179377850) will lead to improvements in intelligence, reportedly by
as much as [3 points in SWE-Bench](https://cookbook.openai.com/examples/responses_api/reasoning_items) (the difference
between SOTA and meh) and cache hit rates improve by 40-80%. In 2026, Agent Traces that progressively expose context to
a coding agent that needs it, will lead to the same kind of performance improvements. In fact, because Agents spend so
much more time in inference-time, the ability to retrieve specific context triggered by code will offer improvements not
just in cost and accuracy, but also in human time wasted resupplying lost context to the agent. Context is king. For the
model labs, as it is for the [agent labs](https://www.latent.space/p/agent-labs) . Conclusion If git tracked "Lines of
Code" as the primary measure of output of the software engineer in the pre-AI era, then Agent Traces are the beginning
of the new era when "Lines of Code" are the commodity, and the new precious resource is context . Whether or not you
have 100% AI commits, your AI Engineers (human or otherwise) will spend the majority of their time crafting and reading
context more than code. We're excited to collaborate on a standard that moves the entire industry forward to meet that
reality, and unlocks a new generation of AI-native developer tooling and coding agent capabilities that make use of
them. Follow us on: Linkedin Twitter [ x ] In this article:
