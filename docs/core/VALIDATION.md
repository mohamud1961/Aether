# Deterministic validation — 13 October 2026

This is an engineering checkpoint, not a benchmark promotion or a claim of improved model performance.
No GLM/the reviewer calls were made. Provider responses in tests were explicitly scripted; commands, files,
terminal processes, images and Docker clones were real.

- Wheel installed into a fresh environment under /tmp outside the source repository. Python isolated mode
  confirmed imports from site-packages. Offline smoke wrote and read a real file and reconstructed two attempts.
- Installed-wheel full suite: 92 passed, 20 skipped on macOS. Skips are explicit Linux/Docker/PTY requirements.
- Linux Docker fault suite: 17 passed in 76.79 seconds against alexgshaw/repair-history:20260403.
  Checks include interactive stdin, Ctrl-C, a 20 MB flood, descendant cleanup, exact exit codes, clone
  isolation/compose routing/cancellation, binary/unterminated files, REPL recovery, zombies and terminal restart.
- A final context-only change adds read_history with stable IDs and character paging; it recovers observations
  even when the sandbox history file cannot be written. Focused installed-wheel history/tool/loop regression: 16 passed after this change; offline real-file smoke passed again.

Linux-tested wheel: `23e1b209ac53dd3c35bc29ee401c78b5707d1c9e0792f318315db3d8e31cc8d0`.
Final wheel: `31bc72f1e6b37bb6fa41f36cba38be66052f7de10d59de91ef56b9202c90fee7`.
Only clm.py, loop.py and tools.py changed between those wheels (history recall). Linux-qualified terminal,
REPL, environment and clone modules are byte-identical. Their qualification is reused; the whole final wheel
is not misreported as the exact binary used in the Linux run.

After log retrieval: no running Docker container, no clone image, no pytest process. VM deallocated and
verified through Azure instance view. No production changes, merges or publication.

Remaining boundaries: full Harbor adapter admission, live provider/reviewer qualification and the matched model
comparison require their own exact protocol and authority. Character-prefix and repeated-read diagnostics
are not token-cache attribution or causal proof of context loss. Read-only concurrency remains opt-in.
