# Regenerate the shipment summary from the current export

The finance dashboard shows more shipped units than the warehouse actually moved. Regenerate the
shipment summary from the export that is in service right now, and write it to `out/summary.json`
(create `out/` if needed).

Counting rules, as the warehouse team defines them:

- An event is one shipment line, identified by its `event_id`. Re-exports can repeat an event, and
  each event counts once.
- Only events with status `ready` count.
- Units are the units figure of each counted event.

The repo is in the current directory. Exports, the legacy file, docs, and logs may disagree with
each other, so decide which export is current from the repo rather than from notes.

The output must be a JSON object with exactly these keys:

- `schema_version`: `shipment_summary.v1`
- `export_path`: the relative path of the export file you used
- `input_sha256`: the SHA-256 of that export file's bytes, lowercase hex
- `accepted_event_count`: integer, the number of counted events
- `accepted_units_total`: integer, the total units of counted events
- `units_by_sku`: object mapping each sku to its units
- `units_by_region`: object mapping each region to its units

Scope: the only file you may create is `out/summary.json`. Do not modify, move, or delete any
existing file, and do not add files anywhere else in the repo.

When done, run `python3 checks/visible_check.py --candidate out/summary.json` from the workspace root
and confirm it reports `passed`.
