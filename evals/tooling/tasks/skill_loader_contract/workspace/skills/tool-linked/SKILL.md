---
name: tool-linked
description: Echo bridge for the QA server
allowed-tools: ["mcp__qa_server__Echo_Tool"]
user-invocable: true
context: null
paths: ["docs/**"]
mcp: ["mcp__qa_server__Echo_Tool"]
hooks: [{"event": "Stop", "matcher": "*"}, {"event": "PostToolUse", "matcher": "Edit"}]
---
# Tool-linked skill

Echo the documentation paths you were given so the QA server can confirm the link.
