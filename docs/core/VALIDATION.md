# Engineering validation — 13 October 2026

All engineering steps 1–6 and accepted self-audit repairs are complete in the declared one-shot
Linux/Harbor envelope. Step 7's matched GLM run is excluded by the latest user instruction.
No live GLM/the reviewer call, merge, production activation or public release was performed.

## Exact final candidate

Executable source: d0192a38bf3fd5c3ed86083f26d2eb532958b6af, version 0.2.0.
Wheel SHA256: 51ea9a134e2140e9f45320f0ebfa8454e5e8d634ef298043972153bae13e33a9.
All 25 installed Python files were compared bytewise to wheel contents. No executable source or
model configuration changed after the final Linux gate. Later commits only seal documentation/evidence.
Final module hashes and exact evidence are in validation-evidence/FINAL_WHEEL.json.

## What was actually exercised

| Gate | Observation | Real failure it catches |
|---|---|---|
| Wheel installed outside repo, Python isolated mode | 119 passed, 22 explicit Linux/Docker/PTY skips; 57.37 s | Hidden source/sibling dependencies; malformed call side effects; lost/changed history; unknown/failed-attempt accounting; real file writes and retrieval; SDK wire/stream faults |
| Same wheel installed in Linux on existing Azure VM | 141 passed, zero skips; 229.32 s | Broken interactive stdin/Ctrl-C/flood handling; unreaped zombies; between-call terminal death; lost log handles; orphan REPL children; wrong-container clone routing; cancellation/cleanup/deadline faults; atomic write errors |
| Actual Harbor 0.20.0 Trial + Docker + AsyncOpenAI HTTP + native grader | Correct project artifact reward 1, deliberately wrong CLM artifact reward 0; 7 fixture requests each; no Harbor exception | Adapter/environment propagation errors; missing real tool effects; grader false-green; request/result mismatch; host credential forwarding; false known usage |
| Research compatibility interfaces | 62 passed, zero skips | Existing callers/fixtures violate complete-review answers or changed runtime contracts |
| Ruff F/E9 and formatting | All checks passed, 43 Python files formatted | Undefined names/import faults and inconsistent code layout; not a correctness proof |

The Harbor trials used an explicitly scripted localhost HTTP fixture, never a real model. They
exercised a named terminal, credential-containment control, stateful Python, file write/read, image,
finish, exact decoded HTTP request reconstruction and native grading. The good/bad rows test the
engineering path and grader; they are not a projected-vs-CLM capability comparison. The independent
shell grader compares the actual final artifact with the task's exact expected bytes. The wrong
artifact earns zero even though the runtime successfully submitted it.

Docker image: alexgshaw/repair-history:20260403.
Image ID: sha256:389b9c8247610c2c5be080b1ac00429007c2c69bf57f7f26c79f0f75ba2d5c74.
Final evidence archive SHA256: 2f343bf51aceeed274778af67ab031aabf35c657315560b683763cb77238b10b.
The enclosing research evidence root is audit_output/aether_worldclass_20261013/full_engineering;
linux-final contains full native tasks, requests, traces, grader output and result rows.
The small evidence set needed to inspect this summary is shipped in docs/validation-evidence.

## Reproduce from this folder

Install dependencies with uv sync --frozen; uv run pytest -q runs the portable suite. On Linux with
Docker and the declared image, set AETHER_FAULT_IMAGE=alexgshaw/repair-history:20260403 to enable the real
fault suite. Install the Harbor extra (uv sync --frozen --extra harbor), then run:

```sh
uv run python examples/harbor_offline_gate.py --image alexgshaw/repair-history:20260403 --out /tmp/aether-harbor-new-evidence
```

The evidence directory must be new. The script clears inherited provider/reviewer settings in its child
and supplies only its explicit localhost fixture configuration. It cannot establish live route
availability or model quality. Docker and the image are explicit OS/runtime prerequisites.

## Honest boundaries

Reviewer reports are fallible advice, never task verification or a finish veto. Null means unknown
usage; billing totals and provider route availability are not certified. Clone snapshots exclude
mounted volumes and running process state. Crash-resume and physical exactly-once effects are not
promised. Read concurrency remains opt-in. Context replay is approximate; character prefixes do not
attribute token-cache misses, and repeated lookup candidates do not prove context-caused failure.
No deterministic result proves world-class task-solving or that all future engineering faults are gone.

## Final ownership checkpoint

All owned tests, native fixture servers, Docker containers and clones are terminal. Required evidence
was retrieved and hash-verified; Azure instance view confirms the run VM is deallocated. Existing
unrelated exited containers were preserved. No active worker agent.

The principal subsequently requested a source/architecture comparison with Prime Agent, Unreal Agent,
Codex, Hermes and OpenCode, then return implementation ownership to the existing Opus task with:
“you have £5 budget, youre in charge\ntest and improve aether as much as possible”.
That is next-phase authority for Opus; GPT-6-Astra's completed engineering gate used no live model calls.
Opus must seal the exact source, route, cases, attempt/retry policy and a spend plan within that
total ceiling before starting model tests. No merge, production activation or public release authority
is implied. The original step 7 remained unexecuted in this engineering phase.
