---
name: alpha-skill
description: Audit code under src with read-only tools
allowed-tools: ["read_file", "grep"]
user-invocable: false
context: fork
paths: ["src/**"]
---
# Alpha skill

Review the files under src/ for missing error handling. Report each finding with its path and line.
Do not edit files. Keep the report to one table.
