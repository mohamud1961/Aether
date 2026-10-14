# Merge rules

1. Read `out/packets/<worker>.json` for each worker. The packet's `packet_version` is the current version for that worker.
2. Read `workers/results/<worker>.json`. A result is accepted only if its `packet_version` equals the current version for that worker.
3. A result with any other version is rejected with reason `stale_packet_version`. Its findings do not enter the merge.
4. Write `out/merged.json` with these keys:
   - `schema_version`: `merged_run.v1`
   - `accepted_workers`: sorted list of accepted worker names
   - `rejected`: list of `{worker, reason, result_packet_version, current_packet_version}`, sorted by worker
   - `findings`: sorted list of the finding `id`s from accepted results only
   - `packet_versions`: object mapping each worker to its current packet version
