# Article

**URL:** https://blog.langchain.com/autonomous-context-compression/

## Content

Skip to content TL;DR: We've added a tool to the [ Deep Agents SDK
](https://docs.langchain.com/oss/python/deepagents/overview?ref=blog.langchain.com) (Python) and [ CLI
](https://docs.langchain.com/oss/python/deepagents/cli/overview?ref=blog.langchain.com) that allows models to compress
their own context windows at opportune times. Motivation [Context
compression](https://blog.langchain.com/context-management-for-deepagents/) is an action that reduces the information in
an agent’s working memory. Older messages are replaced by a summary or condensed representation of an agent’s progress
that preserves what’s relevant to a task. This action is often necessary to accommodate finite context windows and
reduce [context rot](https://research.trychroma.com/context-rot?ref=blog.langchain.com) . Agent harnesses often control
this by compacting at a fixed token threshold ( deepagents uses [model
profiles](https://docs.langchain.com/oss/python/langchain/models?ref=blog.langchain.com#model-profiles) to compact at
85% of any given model’s context limit). This design is suboptimal because there are good times and bad times to
compact: It is not ideal to compact when you’re in the middle of a complex refactor; It is better to compact when you
are starting a new task or otherwise believe that prior context will lose relevance. Many interactive coding tools
feature a /compact command or similar, which allows users to manually trigger a context compression step at opportune
times. We take this one step further in the latest release of deepagents and expose a tool to the agent that lets it
trigger context compression itself. This enables more opportunistic compaction without requiring your application’s
users to be aware of finite context windows or issue specific commands. This tool is currently enabled in [Deep Agents
CLI](https://docs.langchain.com/oss/python/deepagents/cli/overview?ref=blog.langchain.com) and opt-in in the deepagents
SDK. We are generally bullish on the idea that harnesses should, where possible, “get out of the way” and take advantage
of improvements in the underlying reasoning models. This is an instance of [the bitter
lesson](http://www.incompleteideas.net/IncIdeas/BitterLesson.html?ref=blog.langchain.com) : can we give agents more
control over their own context to avoid tuning their harness by hand? When should we compact? There is a variety of
situations that could warrant a context compression action. At clean task boundaries: A user signals that they are
moving on to a new task for which earlier context is likely irrelevant The agent has finished a deliverable and the user
acknowledges task completion After extracting a result from a large amount of context: The agent has obtained a fact,
conclusion, summary, or other result by consuming a significant amount of context, as in a research task Before
consuming a large amount of new context: The agent is about to generate a long draft The agent is about to read a large
amount of new context Before entering a complex multi-step process: The agent is about to start a lengthy refactor,
migration, multi-file edit, or incident response The agent has produced a plan and is about to begin executing the steps
A decision has been made that supersedes prior context: New requirements have come to light that invalidate previous
context There are many tangents or dead-ends that can be reduced to a summary Enumerating all possible scenarios is not
practical, but our observation is that people and LLMs can identify these scenarios and compact at opportune times,
saving the need for a compaction step later on when the context window is nearing its limit. You can read the guidance
we provide the model around this tool in its [system
prompt](https://github.com/langchain-ai/deepagents/blob/537ed6cf153f9f6e50546c9d8674c32587540942/libs/deepagents/deepagents/middleware/summarization.py?ref=blog.langchain.com#L91)
. What happens when the tool is called? The tool is parametrized the same as the existing Deep Agents [summarization
middleware](https://docs.langchain.com/oss/python/deepagents/harness?ref=blog.langchain.com#summarization) : we retain
recent messages (10% of available context) and summarize what comes before. Recent messages, including the call to the
compaction tool and associated response, are retained in the recent context. See [example
trace](https://smith.langchain.com/public/0ff5b066-7377-4922-9269-927e29bd4aba/r?ref=blog.langchain.com) . How to use
The tool is implemented as a separate middleware, so you can enable it by adding it to the middleware list in
create_deep_agent : from deepagents import create_deep_agent from deepagents.backends import StateBackend from
deepagents.middleware.summarization import ( create_summarization_tool_middleware, ) backend = StateBackend # if using
default backend model = "openai:gpt-5.4" agent = create_deep_agent( model=model, middleware=[
create_summarization_tool_middleware(model, backend), ], ) See the SDK
[docs](https://www.notion.so/271808527b178055914cc7e4fdd77897?pvs=21&ref=blog.langchain.com) for more details. In the
CLI, simply call /compact when you’re ready to trim context or move onto a new task. Our experience with this feature We
tuned this feature to be conservative. Deep Agents [preserves all conversation
history](https://docs.langchain.com/oss/python/deepagents/harness?ref=blog.langchain.com#summarization) in its virtual
filesystem, allowing for recovery of context post-summarization, but an erroneous context compression step is
disruptive. We tested: A custom evaluation suite, in which we used (our own) [LangSmith
traces](https://docs.langchain.com/langsmith/observability?ref=blog.langchain.com) to inject follow-up prompts to
threads that do and do not warrant compaction; Terminal-bench-2, in which we did not observe any instances of autonomous
compaction; Our own coding tasks in [Deep Agents
CLI](https://docs.langchain.com/oss/python/deepagents/cli/overview?ref=blog.langchain.com) . In practice agents are
conservative about triggering compaction, but when they do they tend to choose moments where it clearly improves the
workflow. Autonomous context compression is a small feature, but it points at a broader direction for agent design:
giving models more control over their own working memory and fewer rigid, hand-tuned rules in the harness. If you’re
building long-running or interactive agents, try it out in the Deep Agents SDK or CLI and let us know your feedback and
what patterns you’d like to see it handle next. Join our newsletter Updates from the LangChain team and community Enter
your email Processing your application... Success! Please check your inbox and click the link to confirm your
subscription. Sorry, something went wrong. Please try again.
