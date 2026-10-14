---
name: research-auditor
background: true
permissionMode: plan
hooks: [{"event": "SubagentStop", "matcher": "*"}]
mcpServers: ["qa-server", {"name": "inline-probe", "command": "probe-bin"}]
skills: ["alpha-skill", "citation-helper"]
---
Audits research notes in the background. Reports unresolved references to the parent.
