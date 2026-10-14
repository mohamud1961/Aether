# Nightly build notes

- The job is green when `build/run_build.sh` exits 0.
- `[FATAL]` lines on reruns are known noise from the old allocator. Ignore them.
- The count in the summary line is the number of components planned, not the number that finished.

These notes were written before the build config moved to `components_planned`. Treat them as stale.
