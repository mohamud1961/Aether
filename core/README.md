# Aether Core

A self-contained runtime for one-shot work in Linux task containers. The model owns decisions;
the runtime executes tools, manages context and deadlines, and records what happened.

## Install and test

Python 3.12 or newer and `uv` are required for development:

```sh
uv sync --frozen
uv run pytest -q
uv build
```

Install the wheel into any environment; no research checkout or sibling folder is needed.
For Harbor, install the `harbor` extra and select `aether.core.harbor_agent:AetherCoreAgent`.
Linux containers need a shell, standard text utilities, and util-linux `script` for a PTY.
Python in the sandbox enables the persistent REPL. Docker is a runtime prerequisite for Harbor
and optional acceptance-check clones. Package dependencies are declared, not vendored OS tools.

## Interfaces

`aether.core.loop.run_agent` accepts an environment implementing `exec`, `upload_file`, and
`download_file`, a `ChatProvider`, and a `CoreConfig`. `Trace` and `CallLog` record real events
and attempts. No credentials enter the task container through the provider interface.

Tools include named persistent terminals, line-numbered file reads, writes/exact edits, optional
Python REPL, images, and fallible acceptance checks. A long terminal command returns its name
and running state; polling with empty input resumes observation without resubmitting it. Thus named
terminals are also background-job handles. Finish belongs to the model; review cannot veto it.

Projected history and CLM are retained. Long results have saved paths; CLM keeps independent original
message snapshots before destructive context changes. Save failures are reported explicitly.
Optional features and changed prompts require task-level evaluation before claiming a solver gain.

## Verification boundaries

The shipped tests use scripted provider responses with real shell/file effects. They do not establish
model intelligence or benchmark performance. Linux PTY/Docker fault tests skip when prerequisites are
absent; a local macOS pass does not qualify Linux. See docs/ARCHITECTURE.md and docs/LESSONS.md.

This folder is the canonical Core source. The enclosing research checkout retains a compatibility
symlink at aether/core; the package itself neither follows that symlink nor imports the research tree.
The research-only launcher/audit tests stay in the enclosing checkout.
