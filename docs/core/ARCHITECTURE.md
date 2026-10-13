# Ownership and boundaries

- `provider.py` owns client calls, retries and stream assembly; `calls.py` owns attempt identities,
  exact client arguments, responses and unknown usage. A torn final log record is flagged, never success.
- `loop.py` owns ordering, deadlines, dispatch, history transitions and lifecycle. Tool schema validation
  runs before effects; incorrect argument types are repairable errors, never guessed mutations.
- `terminal.py`, `files.py`, `repl.py` own sandbox capabilities. `env.py` owns transfer/process primitives.
- `context.py` projects history; `clm.py` owns editable context and separate original snapshots.
- `review.py`/`oversight.py` own advisory reviews; `questionnaire.py` owns their wire vocabulary.
  `reviewer.py` records a separately bounded transport journal. Its currency accounting is an input estimate,
  not a guaranteed total bill: output pricing is explicitly unknown. No live calls are needed for tests.
- `harbor_agent.py` adapts the runtime to pinned Harbor. `clone.py` owns disposable Docker snapshots.

No skills framework, agent delegation or universal restart/resume system is required by this envelope.
Clean abort and honest partial evidence are required. Background commands use existing terminal sessions,
with at most eight named sessions; no second job registry is maintained.

Linux liveness/restart checks passed on the installed wheel (17 fault tests); read-only concurrency is opt-in (`CoreConfig.parallel_reads=True`), bounded to four
concurrent file reads within a contiguous batch; writes and other tools remain ordering fences; compare any model-facing treatment separately from pure
engineering contracts. Whole-package comparisons do not attribute individual component effects.
