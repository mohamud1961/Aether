# Send the OPS-4471 worker packets and merge what comes back

You are the lead for the October vendor summary refresh. The request thread is in
`thread/request_thread.md`. It has changed direction a few times, so work from the latest decisions.

Turn the thread into three worker packets, one per worker: `ingest`, `reconcile` and `writer`.

- Write each packet to `out/packets/<worker>.json`, with exactly the keys and types in
  `specs/packet_schema.json`. Set `packet_version` to the current version recorded there.
- Put in `constraint_ids` the live constraints that apply to that worker, using the `[C-xx]` ids from the
  thread. Carry every live constraint that applies, and nothing that has been retracted or superseded.
- `goal` says what the worker must do. `inputs`, `outputs` and `done_when` say what it reads, what it
  writes, and when it is finished.

When the workers report back, merge their results into `out/merged.json` following
`specs/merge_rules.md`. The results are in `workers/results/`.

Scope: write only under `out/`. Do not edit the thread, specs, data, vendor files, or the worker results.

`out/merged.json` must be a JSON object with exactly these keys: `schema_version`, `accepted_workers`,
`rejected`, `findings`, `packet_versions`, as `specs/merge_rules.md` defines them. Lists are sorted as
that file says.

When done, run `python3 checks/visible_check.py --candidate out/merged.json` from the workspace root and
confirm it reports `passed`.
