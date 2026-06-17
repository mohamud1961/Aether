# Article

**URL:** https://law.stanford.edu/2026/01/31/from-logging-to-hitl-locating-agent-controls-in-the-ai-life-cycle-core-principles-framework/

## Content

Skip to main content The AI Life Cycles Core Principles (AILCCP) framework* operates through a layered architecture.
Thirty-seven principles articulate what responsible AI systems must achieve. Controls specify how organizations
implement those principles in practice. An AILCCP principle such as Safety declares (among other things) that AI systems
must prevent harm across the application lifecycle. The controls beneath it, including Agent Kill Switch, Sandboxing,
and Rate and Scope Limiter, provide the operational mechanisms through which Safety becomes enforceable. Controls
frequently serve multiple AILCCP principles. Sandboxing, for instance, implements both Safety and Security, because
isolating an agent's execution environment simultaneously prevents harmful actions and resists adversarial exploitation.
This cross-mapping reflects the structural reality that principles are analytically distinct but operationally
entangled. The table below demonstrates that common proposals for agent oversight, including logging, kill switches,
sandboxing, rate limits, human-in-the-loop gates, and transparency requirements, already exist as named controls within
the AILCCP framework. Each maps to one or more AILCCP principles that supply the normative justification for its
deployment. For these mechanisms, the task is selection among existing controls based on the AILCCP principles most
intensely activated by a given agent deployment. Where novel capabilities outpace current controls, the AILCCP framework
accommodates additions through its versioning protocol. Mechanism AILCCP Control(s) Primary Principle(s) Logging
Real-time monitoring, Monitoring & KPIs, Context-to-Output Lineage Accountability, Safety, Security Kill switches Agent
Kill Switch Human-Centered, Safety Sandboxing Sandboxing, Agent tool allowlists and sandbox Safety, Security Rate limits
Rate and Scope Limiter Human-Centered, Safety, Robust Human-in-the-loop Human Approval Gate for Sensitive Actions, HITL
enforcement, Dual-Control for High-Risk Categories Fundamental Rights, Human-Centered, Safety Transparency requirements
AI Fact Label, Provenance/CAI-C2PA pipeline, Evidence & Disclosure Ledger Transparency, Accountability * Here is the
publicly-accessible version of the [AILCCP](https://law.stanford.edu/2023/03/17/ai-life-cycle-core-principles/) . Back
to the Top
