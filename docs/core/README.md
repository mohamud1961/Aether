# Aether Core

A self-contained runtime for one-shot work in Linux task containers. The model owns decisions;
the runtime executes tools, manages context and deadlines, and records what happened.

## Install and test

Python 3.11 or newer is required. Run these commands from the repository root:

```sh
pip install -e ".[dev,vision]"
python -m pytest -q tests/core
```

No research checkout or sibling folder is needed.
The Harbor extra requires Python 3.12 or newer (Harbor 0.20.0's own requirement).
In that environment, install `pip install -e ".[harbor,vision]"` and select `aether.core.harbor_agent:AetherCoreAgent`.
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
absent; a local macOS pass does not qualify Linux. See [ARCHITECTURE.md](ARCHITECTURE.md) and [LESSONS.md](LESSONS.md).

The public layout puts Core in `aether/core/`, its tests in `tests/core/`, and this documentation
in `docs/core/`. Core neither follows a compatibility symlink nor imports the research tree.
The external review transport and research-only launcher/audit tooling are omitted; the shipped
Harbor agent supports review `off` or `contract`. Historical review results describe the original
research environment and cannot all be reproduced from this package alone.

The other documents in this folder preserve the original package layout and validation records.
Use the install commands above for this public layout; those historical records do not qualify
this rewritten package for Linux or establish benchmark performance.

Public curation also normalizes names and prose, including terminology inside prompt strings.
For example, Prime Agent's copied checkpoint prompt uses “principal” where its source uses “user”;
the inherited module attribution describes the original copy. See
[third-party notices](../../THIRD_PARTY_NOTICES.md) for the adapted prompts and licence.
