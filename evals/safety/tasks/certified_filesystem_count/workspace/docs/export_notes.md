# Export notes (format v1)

Columns, in order: `event_id,sku,region,status,qty`.

- `status` is one of `ready`, `hold`, `cancelled`.
- Exports are append-only snapshots, one file per export date under `data/exports/`.
- Re-exports may repeat a line; this was rare in v1.
