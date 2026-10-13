# Ownership and boundaries

Core is a one-shot Linux task runtime. The model chooses actions and completion; the runtime
executes, gives truthful feedback, bounds resource use and preserves inspectable evidence.

| Boundary | Single owner | What callers do not need to manage |
|---|---|---|
| Attempt identity and evidence | calls.py | Reserve-before-dispatch, exact JSON arguments/partial responses, missing usage, open/cancelled/failed attempts, exclusive run namespace |
| Provider transport | provider.py | SDK calls, finite Retry-After bounds, fragmented streams, early EOF, stream closure |
| Run progression | loop.py | Tool/result association, ordering/write fences, context transitions, shared work deadline, independent cleanup |
| Sandbox I/O | env.py | Shared exec/transfer budget, atomic pathname replacement, owned process-tree stopping |
| Capabilities | terminal.py / files.py / repl.py / images.py | Named PTY state and durable generation logs, UTF-8 pages and exact edits, stateful kernel/subcalls, bounded image handling |
| Context | context.py / clm.py / compaction.py | Projected view versus independent originals, stable retrieval IDs, editable mirror, rollback/checkpoints, explicit save failures |
| Advice | review.py / oversight.py / questionnaire.py / contract.py | Validated requested answers and clone-check receipts, fallible findings, no finish veto; verified correctness belongs to a grader |
| Optional the reviewer transport | reviewer.py | Separately bounded attempt journal; input-cost estimate explicitly distinct from unknown output bill |
| Framework and copies | harbor_agent.py / clone.py | Per-trial configuration, host credential filtering, owned provider client closure, host-proven worker identity, disposable Docker resources |

Terminal ownership starts before fallible launch transport and initialization. A lost reply can be
resolved from the owned wrapper PID file during bounded cleanup; unavailable PID evidence is an
explicit cleanup error. Known shells remain owned until successfully stopped. Ready state is separate
from ownership, so failed startup can be retried without treating its partial shell as initialized.
Generation paths use a separator outside the public name alphabet, preserving independent sessions.

Background commands use existing named terminals (maximum eight). Start once, get the session
name/running status, do independent work, poll the same handle. There is no second job registry or
semantic scheduler. Optional parallel reads are at most four contiguous read_file calls; writes and
other tools are ordering fences. CoreConfig.parallel_reads is false by default. Arbitrary shell
commands are not classified as read-only by guessing from strings or paths.

Atomic file writes require one staging file and additional status/commit operations; interrupted
transfers preserve the original. Linux commit uses mv -T to reject a directory destination, including
one created during transfer. Non-Linux local development uses Python os.replace for the same rename
semantics. Python in a Linux sandbox otherwise enables the optional REPL; standard shell/text tools
and util-linux script supply file/PTY capability.

CLM retains original structured messages in host memory and publishes retrievable disk history.
Memory/storage grow with history; mirror/history publication and deep copies have a real cost.
The recorded 10/100/500-turn bench measures builder time/size, not complete transfer latency or a
solver improvement. Save failure is an explicit observation; it never fabricates a usable disk copy.
The original-history tool remains available during that run even when disk publication fails.

No universal restart/resume, skills framework, delegation system or duplicate world-state platform
is required here. Clean abort and honest partial evidence are required. Docker commit is a filesystem
copy with explicit mount/process limitations. Model policies/caps/context selection are preserved;
changing them requires task-level evaluation. Optional capabilities can still change schema cost and
model choices, so mechanical correctness does not establish behavioral no-harm.
