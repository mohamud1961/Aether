# Exec collapse: one round trip per inline write and per fast command

On a remote sandbox every `environment.exec` is a round trip (about 0.2-0.5 s on Modal/Daytona). Two substrate
paths collapsed their exec sequences without changing anything the model sees.

| Path | Before | After |
|---|---|---|
| `put_bytes`, payload <= INLINE_BYTES (48 KB) | 6 execs: resolve, directory check, mkdir, write, chmod, rename | 1 exec |
| `put_bytes`, larger payload | 6 execs + upload | 2 execs + upload: resolve/check/mkdir, then chmod/rename |
| terminal command send | 2 x `put_bytes` + fifo exec + first poll | 1 exec: command file, pending line, fifo, first marker wait |
| fast terminal command, end to end | ~10 execs | 2: the send (which waits in the container) and the read |

The inline script keeps every step and the same atomic rename (`mv -fT` on Linux, `os.replace` elsewhere); each
failing step exits with its own code, mapped to the message that step used to raise. The larger payload keeps
`upload_file`, with one exec before it and one after. A command that outlives the send's 3 s in-container wait falls
back to the unchanged poll loop.

## Equivalence evidence

`tools/core_equiv/equiv.py` compares every environment call, so it differs by design. Captures from the base tree
and from this change, same machine:

    equiv.py run aether-core/src /tmp/equiv-before.json     # base
    equiv.py run aether-core/src /tmp/equiv-after.json      # this change
    equiv.py diff /tmp/equiv-before.json /tmp/equiv-after.json --ignore-env-calls    # 0 differences

All ten scenarios (`basic`, `errors`, `repl`, `retry`, `clm_edit`, `clm_own_all`, `background`, `effort_medium`,
`project_basic`, `project_errors`) differ **only** in `commands` / `env_calls`: provider requests, trace rows, the
RunResult, the final workspace and the control directory are byte-identical. Without the flag the diff reports all
ten (350-596 lines each), all inside those two arrays; base vs base is identical (determinism control).

`test_a_directory_created_during_transfer_is_never_used_as_a_destination` now writes above INLINE_BYTES: the inline
write has no gap between its directory check and its rename to interleave, and the upload path still has one.
